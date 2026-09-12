# Plan: Dataverse Model-Driven App Documentor

## Goal

Given the name of a model-driven app, produce an Excel workbook that lists **every component**
that makes up the app (entities, attributes, forms, views, dashboards, charts, sitemap, business
process flows, web resources, canvas apps) and **every entity the app actually touches** —
not only the ones on the sitemap, but also those reached through form subgrids, timelines
(activity entities), quick view forms, lookup fields, related-navigation relationships, and
view / chart link-entities.

## Why the sitemap is not enough

`appmodulecomponent` rows describe what the maker added to the app: entities (with a
"root component behaviour"), forms, views, charts, dashboards, BPFs, web resources and the
sitemap. Everything the user *sees* inside those forms is implicit:

| Surface | Where the entity reference lives | How this tool finds it |
| --- | --- | --- |
| Sitemap sub-areas | `sitemap.sitemapxml` `SubArea/@Entity`, `@DefaultDashboard`, `$webresource:` URLs | `parsers/sitemap.py` |
| Form fields / attributes | `systemform.formxml` `control/@datafieldname` | `parsers/formxml.py` + `EntityDefinitions(...)/Attributes` |
| Lookup targets | `LookupAttributeMetadata.Targets` for each lookup/customer/owner/partylist field on the form | `metadata.py` |
| Subgrids | `control classid {E7A81278-…}` with `TargetEntityType`, `ViewId`, `RelationshipName` | formxml parser + view fetch |
| Quick view forms | `control classid {5C5600E0-…}` with `QuickFormId/@entityname` | formxml parser + form fetch |
| Timeline / social pane | `control classid {06375649-…}` or PCF `MscrmControls.Timeline.TimelineControl` | activity entities from metadata (`IsActivity`) + `annotation` + `activitypointer` |
| Related navigation | `Navigation/NavBar/NavBarByRelationshipItem/@RelationshipName` | relationship metadata → other side of the relationship |
| Dashboards | `systemform.type in (0,10,13)` — charts/lists carry `TargetEntityType`, `ViewId`, `VisualizationId` | formxml parser |
| Views | `savedquery.fetchxml` `link-entity/@name` | `parsers/fetchxml.py` |
| Charts | `savedqueryvisualization.datadescription` fetch + link-entities | `parsers/fetchxml.py` |
| Business process flows | `workflow.primaryentity`, BPF table (`uniquename`), `clientdata` entity names | `discovery.py` |

## Architecture

```
config.json ──► config.py ──► auth.py (MSAL) ──► client.py (Web API, paging, retry)
                                                       │
                     metadata.py (EntityDefinitions, attributes, relationships – cached)
                                                       │
          discovery.py  ── AppDocumenter.document_app(name) ──► models.AppDocumentation
             │  uses parsers/sitemap.py, parsers/formxml.py, parsers/fetchxml.py
             ▼
          excel.py ──► <app>-app-components-<timestamp>.xlsx  (+ optional JSON)
```

### Walk algorithm

1. Resolve the app (`appmodules` by `name` or `uniquename`).
2. Read `appmodulecomponents` filtered by `_appmoduleidunique_value`.
3. Entities (type 1) become **depth-0** entities. Their `rootcomponentbehavior` decides whether
   *all* of their forms/views/charts are in the app (0) or only the explicitly listed ones (1).
4. Parse the sitemap (type 62): areas, groups, sub-areas → entities, dashboards, web resources.
5. Fetch explicitly listed forms/views/charts (types 60/24, 26, 59), BPFs (29), web resources
   (61), canvas apps (300); anything else is listed by type name from the component-type table.
6. Dashboards (from app components or sitemap) are parsed for lists and charts.
7. Breadth-first **walk** of entities: for every entity with `depth < traversalDepth`, fetch its
   active forms (configurable form types), views and charts, parse them, and *discover* new
   entities at `depth + 1` with a discovery source (Lookup Field, Form Subgrid, Timeline, …).
8. Views and charts referenced only by subgrids/dashboards are fetched and listed at the end.
9. Write one **Components** tab and one **Entities** tab per app plus a **Summary** tab.

`traversalDepth` (default 1) walks the forms of the app's own entities only; the entities they
reference are listed but not walked. Raise it to 2 to also walk the forms of those referenced
entities, and so on.

## Output

**`<App> - Components`**: Component Name · Component Type · Logical / Unique Name ·
Parent Entity · Component Id · Discovery Source · Details

**`<App> - Entities`**: Logical Name · Display Name · Discovery Source · IsCustomEntity ·
All Discovery Sources · Is Activity · Schema Name · Object Type Code · Depth · Referenced By

## Delivery phases

| Phase | Deliverable | Status |
| --- | --- | --- |
| 1 | Config + MSAL auth (client credentials, certificate, interactive, device code, raw token) | done |
| 2 | Web API client with paging, throttling retry, id batching | done |
| 3 | Metadata cache (entities, attributes + lookup targets, relationships) | done |
| 4 | Parsers for sitemap, form XML, FetchXML (unit-tested) | done |
| 5 | Discovery walker with depth control and discovery sources (tested against a fake API) | done |
| 6 | Excel writer (one Components + one Entities tab per app, Summary tab) | done |
| 7 | VS Code launch/tasks, pac CLI helper scripts, Copilot and Claude instructions | done |
| 8 | Validation against a real environment | **needs your tenant** — see README "First run" |

## Open questions / assumptions made

See the "Assumptions and open questions" section in README.md.
