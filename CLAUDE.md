# Claude Code notes for this repository

Purpose: document a Dataverse model-driven app (components + every referenced table) to Excel.

## Run it
```bash
.venv/bin/python document_app.py --list-apps
.venv/bin/python document_app.py --app "<App display or unique name>" -v
.venv/bin/python -m unittest discover -s tests -v
```
First-time: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`, then fill
`config.json` (environmentUrl, auth.tenantId, auth.clientId) and export `DATAVERSE_CLIENT_SECRET`.
Never write secrets into `config.json`; use env vars or the git-ignored `config.local.json`.

## Layout
- `src/dataverse_app_documentor/config.py` – config.json + env overrides, validation
- `auth.py` – MSAL token provider (client credentials / certificate / interactive / device code / raw token)
- `client.py` – Web API GET with paging, 429 retry, id batching
- `metadata.py` – cached EntityDefinitions, attributes (+ lookup Targets), relationships
- `parsers/` – sitemapxml, formxml (tabs/sections/controls/classids), fetchxml
- `discovery.py` – `AppDocumenter.document_app(name)`: the walk (see PLAN.md)
- `excel.py` – workbook writer; `models.py` – row dataclasses; `cli.py` – argparse entry point
- `tests/` – parser tests and a fake-API end-to-end walk; no network needed

## Conventions
- Every entity added to the result goes through `AppDocumenter._discover(doc, state, logical, source, referenced_by, depth)` so the Discovery Source column stays consistent. Add new discovery sources there, and document them in README.md.
- New component kinds: add a `ComponentRow(...)` with a stable `component_type` string; the Excel writer sorts by type.
- Control classids live in `component_types.py`; keep them upper-cased with braces.
- Keep `tests/test_discovery.py::FakeClient` in step with any new Web API query shape.
