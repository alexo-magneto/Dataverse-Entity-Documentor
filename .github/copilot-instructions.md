# Copilot instructions – Dataverse Model-Driven App Documentor

This Python 3.10+ project documents a Dataverse model-driven app into an Excel workbook: a
Components tab (name + type of every form, view, chart, dashboard, sitemap node, attribute,
BPF, web resource…) and an Entities tab (logical name, display name, discovery source, custom flag).

## To run
- Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Configure: edit `config.json` (`environmentUrl`, `auth.tenantId`, `auth.clientId`); put the secret in `DATAVERSE_CLIENT_SECRET`.
- List apps: `.venv/bin/python document_app.py --list-apps`
- Document: `.venv/bin/python document_app.py --app "Sales Hub" -v` → `./output/*.xlsx`
- Tests: `.venv/bin/python -m unittest discover -s tests -v`
- VS Code: Run/Debug "Document app (prompt for name)" or Task "Document app".

## Code map
`src/dataverse_app_documentor/`: `config.py`, `auth.py` (MSAL), `client.py` (Web API), `metadata.py`
(EntityDefinitions cache), `parsers/` (sitemap, formxml, fetchxml), `discovery.py` (walker),
`excel.py`, `cli.py`. Entities are discovered only via `AppDocumenter._discover(...)`; component rows
are `models.ComponentRow`. Use the Dataverse Web API (`/api/data/v9.2/`) only – no SOAP/SDK.

## When asked to extend
- New entity-discovery surface → parse it in `parsers/`, call `_discover` with a new source string, add a test using `tests/test_discovery.py::FakeClient`.
- New output column → `models.py`, `excel.py` headers, and the README table.
