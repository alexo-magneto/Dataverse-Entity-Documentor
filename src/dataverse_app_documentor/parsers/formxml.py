"""Parse systemform.formxml (main forms, quick forms, dashboards) into tabs, sections and controls."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from ..component_types import (
    CLASSID_NOTES_SOCIAL_PANE,
    CLASSID_QUICK_VIEW,
    CLASSID_SUBGRID,
    CONTROL_CLASSIDS,
    LOOKUP_CLASSIDS,
)


@dataclass
class FormControl:
    control_id: str
    classid: str
    datafieldname: str
    kind: str  # Sub Grid | Lookup | Quick View Form | Timeline | Web Resource | Field | Control | ...
    tab: str
    section: str
    unique_id: str = ""
    params: dict[str, str] = field(default_factory=dict)
    quick_forms: list[tuple[str, str]] = field(default_factory=list)  # (entityname, formid)
    custom_control_names: list[str] = field(default_factory=list)
    raw_xml: str = ""

    @property
    def target_entity(self) -> str:
        return (self.params.get("TargetEntityType") or "").lower()

    @property
    def view_id(self) -> str:
        return (self.params.get("ViewId") or "").strip("{}").lower()

    @property
    def visualization_id(self) -> str:
        return (self.params.get("VisualizationId") or "").strip("{}").lower()

    @property
    def relationship_name(self) -> str:
        return self.params.get("RelationshipName") or ""

    @property
    def is_timeline(self) -> bool:
        return self.kind == "Timeline"


@dataclass
class FormTab:
    name: str
    label: str
    sections: list[str] = field(default_factory=list)


@dataclass
class ParsedForm:
    tabs: list[FormTab] = field(default_factory=list)
    controls: list[FormControl] = field(default_factory=list)
    navigation_relationships: list[str] = field(default_factory=list)
    parse_error: str = ""


def _label_of(el: ET.Element) -> str:
    labels = el.find("labels")
    if labels is not None:
        best = ""
        for lbl in labels.findall("label"):
            if lbl.get("languagecode") == "1033" and lbl.get("description"):
                return lbl.get("description", "")
            best = best or lbl.get("description", "")
        if best:
            return best
    return el.get("name") or el.get("id") or ""


def _norm_classid(value: str | None) -> str:
    v = (value or "").strip().upper()
    if v and not v.startswith("{"):
        v = "{" + v + "}"
    return v


def _flatten_params(control: ET.Element) -> dict[str, str]:
    params: dict[str, str] = {}
    p = control.find("parameters")
    if p is None:
        return params
    for child in p:
        text = (child.text or "").strip()
        if text:
            params[child.tag] = text
        # one level of nesting is enough for TargetEntityType etc. inside wrappers
        for sub in child:
            sub_text = (sub.text or "").strip()
            if sub_text and sub.tag not in params:
                params[sub.tag] = sub_text
    return params


def _quick_forms(control: ET.Element) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for qf in control.iter("QuickFormId"):
        ent = (qf.get("entityname") or "").lower()
        fid = (qf.text or "").strip().strip("{}").lower()
        out.append((ent, fid))
    return out


def _classify(control: ET.Element, classid: str, datafieldname: str, custom_controls: list[str], params: dict[str, str]) -> str:
    raw = ET.tostring(control, encoding="unicode")
    ctl_id = (control.get("id") or "").lower()
    ccs = " ".join(custom_controls).lower()
    if classid == CLASSID_SUBGRID and "VisualizationId" in params and "TargetEntityType" in params and not params.get("ViewId"):
        return "Chart"
    if classid == CLASSID_SUBGRID:
        return "Sub Grid"
    if classid == CLASSID_QUICK_VIEW or control.find("QuickForms") is not None or "QuickFormIds" in raw:
        return "Quick View Form"
    if (
        classid == CLASSID_NOTES_SOCIAL_PANE
        or "timeline" in ccs
        or "timelinewallcontrol" in raw.lower()
        or ctl_id in {"timeline", "notescontrol", "socialpane"}
    ):
        return "Timeline"
    if classid in LOOKUP_CLASSIDS:
        return "Lookup"
    if classid in CONTROL_CLASSIDS:
        label = CONTROL_CLASSIDS[classid]
        return label if not datafieldname else "Field"
    if datafieldname:
        return "Field"
    return "Control"


def parse_form_xml(xml: str) -> ParsedForm:
    form = ParsedForm()
    if not xml or not xml.strip():
        return form
    try:
        root = ET.fromstring(xml.strip())
    except ET.ParseError as exc:
        form.parse_error = str(exc)
        return form

    # Custom control (PCF) names keyed by the control's uniqueid/id.
    custom_by_control: dict[str, list[str]] = {}
    for desc in root.iter("controlDescription"):
        key = (desc.get("forControl") or "").strip("{}").lower()
        names = [cc.get("name", "") for cc in desc.iter("customControl") if cc.get("name")]
        if key and names:
            custom_by_control.setdefault(key, []).extend(names)

    seen: set[int] = set()

    def build(control: ET.Element, tab: str, section: str) -> FormControl:
        seen.add(id(control))
        classid = _norm_classid(control.get("classid"))
        datafieldname = (control.get("datafieldname") or "").lower()
        uid = (control.get("uniqueid") or "").strip("{}").lower()
        cid = (control.get("id") or "").strip("{}").lower()
        custom = custom_by_control.get(uid, []) + custom_by_control.get(cid, [])
        params = _flatten_params(control)
        kind = _classify(control, classid, datafieldname, custom, params)
        return FormControl(
            control_id=control.get("id") or "",
            classid=classid,
            datafieldname=datafieldname,
            kind=kind,
            tab=tab,
            section=section,
            unique_id=uid,
            params=params,
            quick_forms=_quick_forms(control),
            custom_control_names=custom,
            raw_xml=ET.tostring(control, encoding="unicode"),
        )

    for tab in root.iter("tab"):
        tab_label = _label_of(tab)
        ft = FormTab(name=tab.get("name") or tab.get("id") or "", label=tab_label)
        for section in tab.iter("section"):
            sec_label = _label_of(section)
            ft.sections.append(sec_label)
            for control in section.iter("control"):
                form.controls.append(build(control, tab_label, sec_label))
        form.tabs.append(ft)

    # Header / footer / anything outside a tab.
    for control in root.iter("control"):
        if id(control) in seen:
            continue
        form.controls.append(build(control, "(header/footer)", ""))

    # Related navigation items (classic Navigation node still present in UCI forms).
    for nav in root.iter("NavBarByRelationshipItem"):
        rel = nav.get("RelationshipName")
        if rel and rel not in form.navigation_relationships:
            form.navigation_relationships.append(rel)

    return form


_TOKEN = re.compile(r"[a-z][a-z0-9_]{2,}")


def tokens_in(text: str) -> set[str]:
    """Lower-cased identifier-like tokens; used to spot activity entity names inside timeline config."""
    return set(_TOKEN.findall((text or "").lower()))
