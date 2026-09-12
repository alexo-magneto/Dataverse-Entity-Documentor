"""Walks a model-driven app and collects every component and referenced entity."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from .client import DataverseClient, DataverseError, odata_quote
from .component_types import (
    COMPONENT_TYPES,
    DASHBOARD_FORM_TYPES,
    FORM_TYPES,
    LOOKUP_ATTRIBUTE_TYPES,
    ROOT_COMPONENT_BEHAVIOR,
    VIEW_TYPES,
    WEB_RESOURCE_TYPES,
    WORKFLOW_CATEGORIES,
)
from .config import DiscoveryConfig
from .metadata import MetadataCache
from .models import AppDocumentation, ComponentRow, EntityRow
from .parsers.fetchxml import parse_fetch_entities
from .parsers.formxml import FormControl, parse_form_xml, tokens_in
from .parsers.sitemap import parse_sitemap_xml

log = logging.getLogger(__name__)

APP_SELECT = "appmoduleid,appmoduleidunique,name,uniquename,description,clienttype,formfactor,navigationtype,statecode,publishedon"
APPCOMP_SELECT = "appmodulecomponentid,objectid,componenttype,rootcomponentbehavior"
FORM_SELECT = "formid,name,type,objecttypecode,formactivationstate,isdefault,description,formxml,uniquename"
VIEW_SELECT = "savedqueryid,name,returnedtypecode,querytype,fetchxml,isdefault,statecode,description"
CHART_SELECT = "savedqueryvisualizationid,name,primaryentitytypecode,datadescription,description"
WORKFLOW_SELECT = "workflowid,name,uniquename,primaryentity,category,type,statecode,clientdata"
WEBRESOURCE_SELECT = "webresourceid,name,displayname,webresourcetype"
SITEMAP_SELECT = "sitemapid,sitemapname,sitemapnameunique,sitemapxml"

# View types that are surfaced inside an app (excludes reporting/outlook/advanced-find internals).
APP_VIEW_TYPES = {0, 2, 4, 64, 1024, 2048, 4096, 16384, 65536}

_BPF_ENTITY_RE = re.compile(r'"(?:entityName|entityLogicalName|primaryEntityName|EntityLogicalName|LogicalName)"\s*:\s*"([a-z0-9_]+)"', re.I)


class AppDocumenter:
    def __init__(self, client: DataverseClient, metadata: MetadataCache, cfg: DiscoveryConfig) -> None:
        self.client = client
        self.meta = metadata
        self.cfg = cfg
        self._exclude = {e.lower() for e in cfg.exclude_entities}
        self._ignore_lookups = {a.lower() for a in cfg.ignore_lookup_attributes}
        self._forms_by_entity: dict[str, list[dict[str, Any]]] = {}
        self._views_by_entity: dict[str, list[dict[str, Any]]] = {}
        self._charts_by_entity: dict[str, list[dict[str, Any]]] = {}

    # ---------------------------------------------------------------- apps
    def list_apps(self) -> list[dict[str, Any]]:
        return self.client.get_all("appmodules", {"$select": APP_SELECT, "$orderby": "name"})

    def find_app(self, name_or_unique_name: str) -> dict[str, Any]:
        q = odata_quote(name_or_unique_name)
        rows = self.client.get_all(
            "appmodules", {"$select": APP_SELECT, "$filter": f"name eq {q} or uniquename eq {q}"}
        )
        if not rows:
            # case-insensitive fallback
            rows = [
                a for a in self.list_apps()
                if a.get("name", "").lower() == name_or_unique_name.lower()
                or a.get("uniquename", "").lower() == name_or_unique_name.lower()
            ]
        if not rows:
            raise DataverseError(f"No model-driven app named '{name_or_unique_name}' was found. Use --list-apps to see names.")
        if len(rows) > 1:
            log.warning("%s apps match '%s'; using the first (%s)", len(rows), name_or_unique_name, rows[0].get("uniquename"))
        return rows[0]

    def _app_components(self, app: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ("appmoduleidunique", "appmoduleid"):
            value = app.get(key)
            if not value:
                continue
            rows = self.client.get_all(
                "appmodulecomponents",
                {"$select": APPCOMP_SELECT, "$filter": f"_appmoduleidunique_value eq {value}"},
            )
            if rows:
                return rows
        return []

    # --------------------------------------------------------------- entry
    def document_app(self, app_name: str) -> AppDocumentation:
        app = self.find_app(app_name)
        doc = AppDocumentation(
            app_name=app.get("name", app_name),
            app_unique_name=app.get("uniquename", ""),
            app_id=app.get("appmoduleid", ""),
            environment_url=self.client.environment_url,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        log.info("Documenting app '%s' (%s)", doc.app_name, doc.app_unique_name)
        self.meta.load_entities()

        state = _WalkState()
        doc.add_component(ComponentRow(doc.app_name, "Model-Driven App", doc.app_unique_name, "", doc.app_id, "AppModule", app.get("description") or ""))

        components = self._app_components(app)
        if not components:
            doc.warnings.append("No appmodulecomponents rows were returned for this app.")
        log.info("App has %s appmodulecomponent rows", len(components))

        by_type: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for c in components:
            by_type[int(c.get("componenttype") or 0)].append(c)

        # 1. Root entities ------------------------------------------------
        for c in by_type.pop(1, []):
            ent = self.meta.entity_by_metadata_id(c["objectid"])
            if ent is None:
                doc.warnings.append(f"Entity component {c['objectid']} could not be resolved in metadata.")
                continue
            behavior = int(c.get("rootcomponentbehavior") if c.get("rootcomponentbehavior") is not None else 0)
            state.behavior[ent.logical_name] = behavior
            doc.add_component(ComponentRow(
                ent.display_name, "Entity", ent.logical_name, "", ent.metadata_id, "AppModuleComponent",
                f"Behavior: {ROOT_COMPONENT_BEHAVIOR.get(behavior, behavior)}"))
            self._discover(doc, state, ent.logical_name, "AppModuleComponent", doc.app_name, 0)

        # 2. Sitemap ------------------------------------------------------
        sitemaps = by_type.pop(62, [])
        if not sitemaps:
            doc.warnings.append("No sitemap component found on the app.")
        for c in sitemaps:
            self._process_sitemap(doc, state, c["objectid"])

        # 3. Explicit forms / views / charts -----------------------------
        for c in by_type.pop(60, []):
            state.explicit_forms.add(c["objectid"].lower())
        for c in by_type.pop(24, []):
            state.explicit_forms.add(c["objectid"].lower())
        for c in by_type.pop(26, []):
            state.explicit_views.add(c["objectid"].lower())
        for c in by_type.pop(59, []):
            state.explicit_charts.add(c["objectid"].lower())

        # 4. Business process flows, web resources, canvas apps, others ----
        for c in by_type.pop(29, []):
            self._process_workflow(doc, state, c["objectid"])
        for c in by_type.pop(61, []):
            self._process_web_resource(doc, c["objectid"], "AppModuleComponent")
        for c in by_type.pop(300, []):
            self._process_canvas_app(doc, c["objectid"])
        for ctype, rows in by_type.items():
            label = COMPONENT_TYPES.get(ctype, f"Component Type {ctype}")
            for c in rows:
                doc.add_component(ComponentRow(c["objectid"], label, "", "", c["objectid"], "AppModuleComponent", f"componenttype={ctype}"))

        # 5. Explicit forms (includes dashboards) ---------------------------
        explicit_form_rows = self.client.get_many_by_ids("systemforms", "formid", state.explicit_forms, FORM_SELECT)
        for form in explicit_form_rows:
            state.form_cache[form["formid"].lower()] = form
        for form in explicit_form_rows:
            ftype = int(form.get("type") or 0)
            if ftype in DASHBOARD_FORM_TYPES:
                self._process_dashboard(doc, state, form, "AppModuleComponent")
            else:
                self._process_form(doc, state, form, 0, "AppModuleComponent")

        # Dashboards referenced only from the sitemap.
        pending_dash = [d for d in state.pending_dashboards if d not in state.processed_forms]
        for form in self.client.get_many_by_ids("systemforms", "formid", pending_dash, FORM_SELECT):
            self._process_dashboard(doc, state, form, "Sitemap")

        # Explicit views / charts.
        for view in self.client.get_many_by_ids("savedqueries", "savedqueryid", state.explicit_views, VIEW_SELECT):
            self._process_view(doc, state, view, 0, "AppModuleComponent")
        for chart in self.client.get_many_by_ids("savedqueryvisualizations", "savedqueryvisualizationid", state.explicit_charts, CHART_SELECT):
            self._process_chart(doc, state, chart, 0, "AppModuleComponent")

        # 6. Walk entities (breadth-first, depth-limited) ------------------
        while state.queue:
            logical, depth = state.queue.popleft()
            if logical in state.walked:
                continue
            state.walked.add(logical)
            self._walk_entity(doc, state, logical, depth)

        # 7. Views / charts referenced by subgrids and dashboards ----------
        pending_views = [v for v in state.pending_views if v not in state.processed_views]
        for view in self.client.get_many_by_ids("savedqueries", "savedqueryid", pending_views, VIEW_SELECT):
            self._process_view(doc, state, view, 1, state.pending_view_sources.get(view["savedqueryid"].lower(), "Form Subgrid"))
        pending_charts = [c for c in state.pending_charts if c not in state.processed_charts]
        for chart in self.client.get_many_by_ids("savedqueryvisualizations", "savedqueryvisualizationid", pending_charts, CHART_SELECT):
            self._process_chart(doc, state, chart, 1, state.pending_chart_sources.get(chart["savedqueryvisualizationid"].lower(), "Chart"))
        pending_qv = [f for f in state.pending_quick_forms if f not in state.processed_forms]
        for form in self.client.get_many_by_ids("systemforms", "formid", pending_qv, FORM_SELECT):
            self._add_form_row(doc, form, "Quick View Form")

        # 8. Attribute scope "all": every attribute of every discovered entity.
        if self.cfg.attribute_scope == "all":
            for logical in sorted(doc.entities):
                for attr in self.meta.attributes(logical).values():
                    doc.add_component(ComponentRow(attr.display_name, "Attribute", attr.logical_name, logical, "", "Entity Metadata", attr.attribute_type))

        log.info("Done: %s components, %s entities, %s requests", len(doc.components), len(doc.entities), self.client.request_count)
        return doc

    # ------------------------------------------------------------ discover
    def _discover(self, doc: AppDocumentation, state: "_WalkState", logical: str, source: str, referenced_by: str, depth: int) -> EntityRow | None:
        logical = (logical or "").lower().strip()
        if not logical or logical in self._exclude:
            return None
        ent = self.meta.entity(logical)
        if ent is None:
            if logical not in state.unresolved:
                state.unresolved.add(logical)
                doc.warnings.append(f"Referenced entity '{logical}' (via {source}: {referenced_by}) does not exist in metadata; skipped.")
            return None
        row = doc.entities.get(logical)
        if row is None:
            row = EntityRow(
                logical_name=ent.logical_name,
                display_name=ent.display_name,
                is_custom_entity=ent.is_custom,
                is_activity=ent.is_activity,
                schema_name=ent.schema_name,
                object_type_code=ent.object_type_code,
                depth=depth,
                is_managed=ent.is_managed,
            )
            doc.entities[logical] = row
        if source not in row.discovery_sources:
            row.discovery_sources.append(source)
        if referenced_by and referenced_by not in row.referenced_by and len(row.referenced_by) < 50:
            row.referenced_by.append(referenced_by)
        if depth < row.depth:
            row.depth = depth
        if row.depth < self.cfg.traversal_depth:
            if logical not in state.walked and logical not in state.queued:
                state.queued.add(logical)
                state.queue.append((logical, row.depth))
        return row

    # ------------------------------------------------------------- sitemap
    def _process_sitemap(self, doc: AppDocumentation, state: "_WalkState", sitemap_id: str) -> None:
        sm = self.client.get_by_id("sitemaps", sitemap_id, SITEMAP_SELECT)
        if sm is None:
            doc.warnings.append(f"Sitemap {sitemap_id} not found.")
            return
        doc.add_component(ComponentRow(sm.get("sitemapname") or "Site Map", "Site Map", sm.get("sitemapnameunique") or "", "", sm["sitemapid"], "AppModuleComponent"))
        try:
            nodes = parse_sitemap_xml(sm.get("sitemapxml") or "")
        except Exception as exc:
            doc.warnings.append(f"Sitemap XML could not be parsed: {exc}")
            return
        for node in nodes:
            if node.entity and (not node.title or node.title == node.id):
                ent = self.meta.entity(node.entity)
                if ent:
                    node.title = ent.display_name
            details = []
            if node.entity:
                details.append(f"Entity: {node.entity}")
            if node.url:
                details.append(f"Url: {node.url}")
            if node.dashboard_id:
                details.append(f"DefaultDashboard: {node.dashboard_id}")
            doc.add_component(ComponentRow(node.title or node.id, f"Sitemap {node.kind}", node.id, node.entity, "", "Sitemap", " | ".join(details) or node.path))
            if node.entity:
                self._discover(doc, state, node.entity, "Sitemap", node.path, 0)
            if node.dashboard_id:
                state.pending_dashboards.append(node.dashboard_id)
            if node.web_resource:
                self._process_web_resource_by_name(doc, node.web_resource, "Sitemap")

    # ---------------------------------------------------------------- walk
    def _walk_entity(self, doc: AppDocumentation, state: "_WalkState", logical: str, depth: int) -> None:
        ent = self.meta.entity(logical)
        if ent is None:
            return
        behavior = state.behavior.get(logical, 0)
        explicit_only = depth == 0 and behavior == 1
        log.info("Walking entity %s (depth %s, behavior %s)", logical, depth, ROOT_COMPONENT_BEHAVIOR.get(behavior))

        forms = self._entity_forms(logical)
        for form in forms:
            fid = form["formid"].lower()
            ftype = int(form.get("type") or 0)
            if ftype in DASHBOARD_FORM_TYPES:
                continue
            if explicit_only and fid not in state.explicit_forms:
                continue
            if ftype not in self.cfg.form_types and fid not in state.explicit_forms:
                continue
            self._process_form(doc, state, form, depth, "AppModuleComponent" if fid in state.explicit_forms else "Entity Forms")

        if self.cfg.include_views:
            for view in self._entity_views(logical):
                vid = view["savedqueryid"].lower()
                if explicit_only and vid not in state.explicit_views:
                    continue
                if int(view.get("querytype") or 0) not in APP_VIEW_TYPES and vid not in state.explicit_views:
                    continue
                self._process_view(doc, state, view, depth, "AppModuleComponent" if vid in state.explicit_views else "Entity Views")

        if self.cfg.include_charts:
            for chart in self._entity_charts(logical):
                cid = chart["savedqueryvisualizationid"].lower()
                if explicit_only and cid not in state.explicit_charts:
                    continue
                self._process_chart(doc, state, chart, depth, "AppModuleComponent" if cid in state.explicit_charts else "Entity Charts")

        if self.cfg.include_all_relationships:
            for rel in self.meta.relationships(logical):
                other = rel.other_entity(logical)
                if other and other != logical:
                    doc.add_component(ComponentRow(rel.schema_name, f"Relationship ({rel.kind})", rel.schema_name, logical, "", "Entity Relationship", f"{logical} -> {other}"))
                    self._discover(doc, state, other, "Entity Relationship", f"{rel.schema_name} ({rel.kind})", depth + 1)

    # ------------------------------------------------------------- fetches
    def _entity_forms(self, logical: str) -> list[dict[str, Any]]:
        if logical in self._forms_by_entity:
            return self._forms_by_entity[logical]
        flt = f"objecttypecode eq {odata_quote(logical)}"
        if not self.cfg.include_inactive_forms:
            flt += " and formactivationstate eq 1"
        rows = self.client.get_all("systemforms", {"$select": FORM_SELECT, "$filter": flt})
        self._forms_by_entity[logical] = rows
        return rows

    def _entity_views(self, logical: str) -> list[dict[str, Any]]:
        if logical in self._views_by_entity:
            return self._views_by_entity[logical]
        rows = self.client.get_all("savedqueries", {"$select": VIEW_SELECT, "$filter": f"returnedtypecode eq {odata_quote(logical)} and statecode eq 0"})
        self._views_by_entity[logical] = rows
        return rows

    def _entity_charts(self, logical: str) -> list[dict[str, Any]]:
        if logical in self._charts_by_entity:
            return self._charts_by_entity[logical]
        rows = self.client.get_all("savedqueryvisualizations", {"$select": CHART_SELECT, "$filter": f"primaryentitytypecode eq {odata_quote(logical)}"})
        self._charts_by_entity[logical] = rows
        return rows

    # --------------------------------------------------------------- forms
    def _add_form_row(self, doc: AppDocumentation, form: dict[str, Any], source: str) -> str:
        ftype = int(form.get("type") or 0)
        type_name = FORM_TYPES.get(ftype, f"Form Type {ftype}")
        entity = (form.get("objecttypecode") or "").lower()
        if entity == "none":
            entity = ""
        state_name = "Active" if int(form.get("formactivationstate") or 1) == 1 else "Inactive"
        details = f"{state_name}; Default: {bool(form.get('isdefault'))}"
        doc.add_component(ComponentRow(form.get("name") or form["formid"], type_name, form.get("uniquename") or "", entity, form["formid"], source, details))
        return type_name

    def _process_form(self, doc: AppDocumentation, state: "_WalkState", form: dict[str, Any], depth: int, source: str) -> None:
        fid = form["formid"].lower()
        if fid in state.processed_forms:
            return
        state.processed_forms.add(fid)
        form_name = form.get("name") or fid
        entity = (form.get("objecttypecode") or "").lower()
        type_name = self._add_form_row(doc, form, source)
        parsed = parse_form_xml(form.get("formxml") or "")
        if parsed.parse_error:
            doc.warnings.append(f"Form '{form_name}' ({entity}) XML could not be parsed: {parsed.parse_error}")
            return
        ent_meta = self.meta.entity(entity)
        attrs = self.meta.attributes(entity) if (self.cfg.attribute_scope == "form" and ent_meta) else {}
        ref = f"{form_name} ({type_name})"

        for tab in parsed.tabs:
            doc.add_component(ComponentRow(tab.label or tab.name, "Form Tab", tab.name, entity, "", "Form", f"Form: {form_name}; Sections: {', '.join(s for s in tab.sections if s)}"))

        for ctl in parsed.controls:
            self._process_control(doc, state, ctl, entity, ent_meta, attrs, ref, depth, form_name)

        for rel_name in parsed.navigation_relationships:
            rel = self.meta.relationship_by_name(entity, rel_name) if ent_meta else None
            other = rel.other_entity(entity) if rel else ""
            doc.add_component(ComponentRow(rel_name, "Form Navigation (Related)", rel_name, entity, "", "Form", f"Form: {form_name}; Related entity: {other or 'unknown'}"))
            if other:
                self._discover(doc, state, other, "Form Navigation (Relationship)", f"{rel_name} on {ref}", depth + 1)

    def _process_control(self, doc, state, ctl: FormControl, entity: str, ent_meta, attrs, ref: str, depth: int, form_name: str) -> None:
        where = f"Form: {form_name}; Tab: {ctl.tab}; Section: {ctl.section}"

        # Attributes on the form (and their lookup targets).
        if ctl.datafieldname and self.cfg.attribute_scope != "none":
            attr = attrs.get(ctl.datafieldname)
            display = attr.display_name if attr else ctl.datafieldname
            atype = attr.attribute_type if attr else "(unknown)"
            if self.cfg.attribute_scope == "form":
                doc.add_component(ComponentRow(display, "Attribute (Form Field)", ctl.datafieldname, entity, "", "Form", f"Type: {atype}; {where}"))
            targets = list(attr.targets) if attr else []
            is_lookup = (attr is not None and attr.attribute_type in LOOKUP_ATTRIBUTE_TYPES) or ctl.kind == "Lookup"
            if is_lookup and ctl.datafieldname not in self._ignore_lookups:
                for target in targets:
                    self._discover(doc, state, target, "Lookup Field", f"{entity}.{ctl.datafieldname} on {ref}", depth + 1)

        if ctl.kind == "Sub Grid":
            target = ctl.target_entity
            rel_note = f"; Relationship: {ctl.relationship_name}" if ctl.relationship_name else ""
            doc.add_component(ComponentRow(ctl.control_id, "Form Subgrid", ctl.control_id, entity, ctl.view_id, "Form", f"Target: {target or '?'}{rel_note}; {where}"))
            if target:
                self._discover(doc, state, target, "Form Subgrid", f"{ctl.control_id} on {ref}", depth + 1)
            elif ctl.relationship_name and ent_meta:
                rel = self.meta.relationship_by_name(entity, ctl.relationship_name)
                if rel:
                    self._discover(doc, state, rel.other_entity(entity), "Form Subgrid", f"{ctl.control_id} on {ref}", depth + 1)
            if ctl.view_id:
                state.pending_views.append(ctl.view_id)
                state.pending_view_sources.setdefault(ctl.view_id, "Form Subgrid")
        elif ctl.kind == "Chart":
            target = ctl.target_entity
            doc.add_component(ComponentRow(ctl.control_id, "Form Chart", ctl.control_id, entity, ctl.visualization_id, "Form", f"Target: {target or '?'}; {where}"))
            if target:
                self._discover(doc, state, target, "Chart", f"{ctl.control_id} on {ref}", depth + 1)
            if ctl.visualization_id:
                state.pending_charts.append(ctl.visualization_id)
                state.pending_chart_sources.setdefault(ctl.visualization_id, "Form Chart")
            if ctl.view_id:
                state.pending_views.append(ctl.view_id)
                state.pending_view_sources.setdefault(ctl.view_id, "Form Chart")
        elif ctl.kind == "Quick View Form":
            for qv_entity, qv_form_id in ctl.quick_forms:
                doc.add_component(ComponentRow(ctl.control_id, "Form Quick View Control", ctl.control_id, entity, qv_form_id, "Form", f"Target: {qv_entity}; Lookup: {ctl.datafieldname}; {where}"))
                if qv_entity:
                    self._discover(doc, state, qv_entity, "Quick View Form", f"{ctl.control_id} on {ref}", depth + 1)
                if qv_form_id:
                    state.pending_quick_forms.append(qv_form_id)
        elif ctl.kind == "Timeline":
            doc.add_component(ComponentRow(ctl.control_id or "Timeline", "Form Timeline", ctl.control_id, entity, "", "Form", where))
            self._discover_timeline_entities(doc, state, ctl, entity, ent_meta, ref, depth)
        elif ctl.kind == "Web Resource":
            name = ctl.params.get("Url") or ctl.params.get("url") or ctl.control_id
            doc.add_component(ComponentRow(name, "Form Web Resource", name, entity, "", "Form", where))
        elif ctl.kind == "IFrame":
            doc.add_component(ComponentRow(ctl.control_id, "Form IFrame", ctl.control_id, entity, "", "Form", f"Url: {ctl.params.get('Url', '')}; {where}"))
        elif ctl.custom_control_names:
            names = ", ".join(dict.fromkeys(ctl.custom_control_names))
            doc.add_component(ComponentRow(names, "Custom Control (PCF)", names, entity, "", "Form", f"Control: {ctl.control_id}; Field: {ctl.datafieldname}; {where}"))

    def _discover_timeline_entities(self, doc, state, ctl: FormControl, entity: str, ent_meta, ref: str, depth: int) -> None:
        activity_names = {a.logical_name for a in self.meta.activity_entities()}
        found = tokens_in(ctl.raw_xml) & activity_names
        if self.cfg.timeline_include_all_activity_entities or not found:
            found = set(activity_names)
        if self.meta.entity("activitypointer") is not None:
            found.add("activitypointer")
        if ent_meta is None or ent_meta.has_notes or "annotation" in tokens_in(ctl.raw_xml):
            found.add("annotation")
        for name in sorted(found):
            self._discover(doc, state, name, "Timeline", f"{ctl.control_id or 'Timeline'} on {ref}", depth + 1)

    # ---------------------------------------------------------- dashboards
    def _process_dashboard(self, doc: AppDocumentation, state: "_WalkState", form: dict[str, Any], source: str) -> None:
        fid = form["formid"].lower()
        if fid in state.processed_forms:
            return
        state.processed_forms.add(fid)
        name = form.get("name") or fid
        ftype = int(form.get("type") or 0)
        entity = (form.get("objecttypecode") or "").lower()
        if entity == "none":
            entity = ""
        doc.add_component(ComponentRow(name, FORM_TYPES.get(ftype, "Dashboard"), form.get("uniquename") or "", entity, form["formid"], source))
        parsed = parse_form_xml(form.get("formxml") or "")
        if parsed.parse_error:
            doc.warnings.append(f"Dashboard '{name}' XML could not be parsed: {parsed.parse_error}")
            return
        ref = f"Dashboard: {name}"
        if entity:
            self._discover(doc, state, entity, "Dashboard", ref, 1)
        for ctl in parsed.controls:
            target = ctl.target_entity
            if ctl.kind in {"Sub Grid", "Chart"}:
                label = "Dashboard Chart" if ctl.visualization_id else "Dashboard List"
                doc.add_component(ComponentRow(ctl.control_id, label, ctl.control_id, target, ctl.visualization_id or ctl.view_id, "Dashboard", f"{ref}; Tab: {ctl.tab}"))
                if target:
                    self._discover(doc, state, target, "Dashboard", f"{ctl.control_id} on {ref}", 1)
                if ctl.view_id:
                    state.pending_views.append(ctl.view_id)
                    state.pending_view_sources.setdefault(ctl.view_id, "Dashboard")
                if ctl.visualization_id:
                    state.pending_charts.append(ctl.visualization_id)
                    state.pending_chart_sources.setdefault(ctl.visualization_id, "Dashboard")
            elif ctl.kind == "Timeline":
                doc.add_component(ComponentRow(ctl.control_id or "Timeline", "Dashboard Timeline", ctl.control_id, entity, "", "Dashboard", ref))
                self._discover_timeline_entities(doc, state, ctl, entity, self.meta.entity(entity), ref, 0)
            elif ctl.kind == "Web Resource":
                name_wr = ctl.params.get("Url") or ctl.control_id
                doc.add_component(ComponentRow(name_wr, "Dashboard Web Resource", name_wr, "", "", "Dashboard", ref))
            elif ctl.kind == "IFrame":
                doc.add_component(ComponentRow(ctl.control_id, "Dashboard IFrame", ctl.control_id, "", "", "Dashboard", f"Url: {ctl.params.get('Url', '')}; {ref}"))
            elif target:
                doc.add_component(ComponentRow(ctl.control_id, "Dashboard Component", ctl.control_id, target, "", "Dashboard", ref))
                self._discover(doc, state, target, "Dashboard", f"{ctl.control_id} on {ref}", 1)

    # --------------------------------------------------------- views/charts
    def _process_view(self, doc: AppDocumentation, state: "_WalkState", view: dict[str, Any], depth: int, source: str) -> None:
        vid = view["savedqueryid"].lower()
        if vid in state.processed_views:
            return
        state.processed_views.add(vid)
        entity = (view.get("returnedtypecode") or "").lower()
        qtype = int(view.get("querytype") or 0)
        primary, linked = parse_fetch_entities(view.get("fetchxml") or "")
        details = f"{VIEW_TYPES.get(qtype, f'Query Type {qtype}')}; Default: {bool(view.get('isdefault'))}"
        if linked:
            details += f"; Linked: {', '.join(linked)}"
        doc.add_component(ComponentRow(view.get("name") or vid, "View", "", entity or primary, vid, source, details))
        if entity and entity not in doc.entities:
            self._discover(doc, state, entity, source, f"View: {view.get('name')}", depth + 1)
        for link in linked:
            self._discover(doc, state, link, "View Link-Entity", f"{view.get('name')} ({entity})", depth + 1)

    def _process_chart(self, doc: AppDocumentation, state: "_WalkState", chart: dict[str, Any], depth: int, source: str) -> None:
        cid = chart["savedqueryvisualizationid"].lower()
        if cid in state.processed_charts:
            return
        state.processed_charts.add(cid)
        entity = (chart.get("primaryentitytypecode") or "").lower()
        primary, linked = parse_fetch_entities(chart.get("datadescription") or "")
        details = f"Linked: {', '.join(linked)}" if linked else ""
        doc.add_component(ComponentRow(chart.get("name") or cid, "Chart", "", entity or primary, cid, source, details))
        if entity and entity not in doc.entities:
            self._discover(doc, state, entity, "Chart", f"Chart: {chart.get('name')}", depth + 1)
        for link in linked:
            self._discover(doc, state, link, "Chart", f"{chart.get('name')} ({entity})", depth + 1)

    # ------------------------------------------------ workflows / resources
    def _process_workflow(self, doc: AppDocumentation, state: "_WalkState", workflow_id: str) -> None:
        wf = self.client.get_by_id("workflows", workflow_id, WORKFLOW_SELECT)
        if wf is None:
            doc.add_component(ComponentRow(workflow_id, "Process (Workflow)", "", "", workflow_id, "AppModuleComponent", "Workflow record not found"))
            return
        category = int(wf.get("category") if wf.get("category") is not None else 0)
        label = WORKFLOW_CATEGORIES.get(category, "Process")
        primary = (wf.get("primaryentity") or "").lower()
        doc.add_component(ComponentRow(wf.get("name") or workflow_id, label, wf.get("uniquename") or "", primary, wf["workflowid"], "AppModuleComponent"))
        if primary:
            self._discover(doc, state, primary, label, wf.get("name") or workflow_id, 1)
        if category == 4:
            bpf_entity = (wf.get("uniquename") or "").lower()
            if bpf_entity and self.meta.entity(bpf_entity):
                self._discover(doc, state, bpf_entity, "Business Process Flow", f"BPF table for {wf.get('name')}", 1)
            for name in set(_BPF_ENTITY_RE.findall(wf.get("clientdata") or "")):
                if self.meta.entity(name.lower()):
                    self._discover(doc, state, name.lower(), "Business Process Flow", wf.get("name") or workflow_id, 1)

    def _process_web_resource(self, doc: AppDocumentation, webresource_id: str, source: str) -> None:
        wr = self.client.get_by_id("webresources", webresource_id, WEBRESOURCE_SELECT)
        if wr is None:
            doc.add_component(ComponentRow(webresource_id, "Web Resource", "", "", webresource_id, source, "Web resource not found"))
            return
        wtype = int(wr.get("webresourcetype") or 0)
        doc.add_component(ComponentRow(wr.get("displayname") or wr.get("name") or webresource_id, "Web Resource", wr.get("name") or "", "", wr["webresourceid"], source, WEB_RESOURCE_TYPES.get(wtype, str(wtype))))

    def _process_web_resource_by_name(self, doc: AppDocumentation, name: str, source: str) -> None:
        try:
            rows = self.client.get_all("webresources", {"$select": WEBRESOURCE_SELECT, "$filter": f"name eq {odata_quote(name)}"})
        except DataverseError:
            rows = []
        if rows:
            wr = rows[0]
            wtype = int(wr.get("webresourcetype") or 0)
            doc.add_component(ComponentRow(wr.get("displayname") or name, "Web Resource", name, "", wr["webresourceid"], source, WEB_RESOURCE_TYPES.get(wtype, str(wtype))))
        else:
            doc.add_component(ComponentRow(name, "Web Resource", name, "", "", source, "Referenced by sitemap"))

    def _process_canvas_app(self, doc: AppDocumentation, canvas_id: str) -> None:
        try:
            ca = self.client.get_by_id("canvasapps", canvas_id, "canvasappid,name,displayname")
        except DataverseError:
            ca = None
        if ca:
            doc.add_component(ComponentRow(ca.get("displayname") or ca.get("name") or canvas_id, "Canvas App", ca.get("name") or "", "", ca["canvasappid"], "AppModuleComponent"))
        else:
            doc.add_component(ComponentRow(canvas_id, "Canvas App", "", "", canvas_id, "AppModuleComponent"))


class _WalkState:
    def __init__(self) -> None:
        self.behavior: dict[str, int] = {}
        self.explicit_forms: set[str] = set()
        self.explicit_views: set[str] = set()
        self.explicit_charts: set[str] = set()
        self.form_cache: dict[str, dict[str, Any]] = {}
        self.processed_forms: set[str] = set()
        self.processed_views: set[str] = set()
        self.processed_charts: set[str] = set()
        self.pending_dashboards: list[str] = []
        self.pending_views: list[str] = []
        self.pending_view_sources: dict[str, str] = {}
        self.pending_charts: list[str] = []
        self.pending_chart_sources: dict[str, str] = {}
        self.pending_quick_forms: list[str] = []
        self.queue: deque[tuple[str, int]] = deque()
        self.queued: set[str] = set()
        self.walked: set[str] = set()
        self.unresolved: set[str] = set()
