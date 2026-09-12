# Dataverse Model-Driven App Documentor

Produces an Excel workbook that documents **everything a model-driven app is made of** and
**every Dataverse table it reaches** — including the tables that never appear on the sitemap but
are pulled in through form subgrids, timelines (activities), quick view forms, lookup columns,
related-record navigation, dashboards, views and charts.

Runs from a terminal, VS Code (Run/Debug and Tasks), Claude Code, or GitHub Copilot Chat.
Authenticates with an Entra ID app registration (client id/secret or certificate) or an
interactive / device-code sign-in. Power Platform CLI helper scripts are included for
environment discovery.

## Contents of the workbook

| Tab | What it contains |
| --- | --- |
| `Summary` | App name, unique name, id, environment, generation time, counts per component type, warnings |
| `<App> - Components` | One row per component: **Component Name**, **Component Type**, Logical / Unique Name, Parent Entity, Component Id, Discovery Source, Details |
| `<App> - Entities` | One row per table: **Logical Name**, **Display Name**, **Discovery Source**, **IsCustomEntity**, All Discovery Sources, Is Activity, Schema Name, Object Type Code, Depth, Referenced By |

Component types written include: Model-Driven App, Entity, Attribute (Form Field), Main Form,
Quick Create Form, Quick View Form, Card Form, Form Tab, Form Subgrid, Form Timeline, Form Quick
View Control, Form Navigation (Related), Form Web Resource, Custom Control (PCF), View, Chart,
Dashboard, Dashboard Chart, Dashboard List, Site Map, Sitemap Area, Sitemap Group, Sitemap
SubArea, Business Process Flow, Web Resource, Canvas App, and any other `appmodulecomponent`
type by name.

Discovery sources for entities: `AppModuleComponent`, `Sitemap`, `Dashboard`, `Lookup Field`,
`Form Subgrid`, `Quick View Form`, `Timeline`, `Form Navigation (Relationship)`,
`View Link-Entity`, `Chart`, `Business Process Flow`, `Entity Relationship` (opt-in).

If you document several apps in one run, each app gets its own pair of tabs in one workbook
(or use `--separate-workbooks`).

## Prerequisites

* Python 3.10+ (`python3 --version`)
* Access to the Dataverse environment with a security role that can read customisations
  (System Administrator / System Customizer, or a custom role with read on App, App Module
  Component, Site Map, System Form, View, System Chart, Process, Web Resource, Canvas App and
  Customizations).
* For unattended use: an **Entra ID app registration** and an **application user** in the
  environment (steps below).
* Optional: [Power Platform CLI](https://learn.microsoft.com/power-platform/developer/cli/introduction)
  (`pac`) for environment discovery, and Azure CLI (`az`) as an alternative token source.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

On Windows: `py -3 -m venv .venv` then `.venv\Scripts\pip install -r requirements.txt`.

Or in VS Code: **Terminal → Run Task → "Setup: create venv and install dependencies"**.

### 1. Create the app registration (once per tenant)

1. Entra admin center → **App registrations → New registration**. Single tenant. No redirect URI
   needed for client credentials (add `http://localhost` as a *Mobile and desktop* redirect if you
   want `interactive` mode).
2. Copy the **Application (client) ID** and **Directory (tenant) ID** into `config.json`.
3. **Certificates & secrets** → create a client secret (or upload a certificate). Store the
   secret in the `DATAVERSE_CLIENT_SECRET` environment variable rather than in the file.
4. Power Platform admin center → your environment → **Settings → Users + permissions →
   Application users → New app user** → pick the registration, a business unit, and assign
   **System Administrator** (or a read-only customisation role).

### 2. Fill in `config.json`

```jsonc
{
  "environmentUrl": "https://contoso.crm.dynamics.com",
  "auth": {
    "mode": "clientCredentials",          // clientCredentials | clientCertificate | interactive | deviceCode | accessToken
    "tenantId": "<tenant guid>",
    "clientId": "<application (client) id>",
    "clientSecret": ""                    // leave empty and set DATAVERSE_CLIENT_SECRET instead
  },
  "apps": ["Sales Hub"],                  // display names or unique names; --app overrides
  "output": { "directory": "./output", "fileName": "{app}-app-components-{timestamp}.xlsx" },
  "discovery": { "traversalDepth": 1, "attributeScope": "form" }
}
```

The file is validated against `config.schema.json` in VS Code. `config.local.json` (git-ignored)
is loaded in preference to `config.json` if it exists, and `configf.json` is also accepted.
Environment variables `DATAVERSE_URL`, `DATAVERSE_TENANT_ID`, `DATAVERSE_CLIENT_ID`,
`DATAVERSE_CLIENT_SECRET`, `DATAVERSE_AUTH_MODE`, `DATAVERSE_ACCESS_TOKEN` override the file.

Auth modes:

| mode | needs | use when |
| --- | --- | --- |
| `clientCredentials` | tenantId, clientId, secret | unattended / CI |
| `clientCertificate` | tenantId, clientId, certificatePath (PEM), certificateThumbprint | unattended without secrets |
| `interactive` | clientId (public client with `http://localhost` redirect) | you sign in with a browser; token cached under `~/.dataverse-app-documentor/` |
| `deviceCode` | clientId | headless machines; prints a code to enter at microsoft.com/devicelogin |
| `accessToken` | `DATAVERSE_ACCESS_TOKEN` env var | `az account get-access-token --resource <env url>` (see `scripts/get-token-with-az.sh`) |

### 3. First run

```bash
.venv/bin/python document_app.py --whoami          # connection test
.venv/bin/python document_app.py --list-apps       # find the app name
.venv/bin/python document_app.py --app "Sales Hub" -v
```

The workbook is written to `./output/`. Add `--json` to also get the raw model as JSON.

## Running from each tool

**VS Code** – Run and Debug panel: *Document app (prompt for name)*, *List model-driven apps*,
*Test connection*. Tasks (`Ctrl/Cmd+Shift+B` runs *Document app*). Recommended extensions are
suggested on first open.

**Terminal / Claude Code** – `CLAUDE.md` tells Claude how the repo works; ask it e.g.
"document the Customer Service Hub app and summarise which custom tables it uses".

**GitHub Copilot Chat** – `.github/copilot-instructions.md` gives Copilot the same context. In the
chat, `@workspace document the "Sales Hub" app` will propose the correct command.

**Power Platform CLI** – `bash scripts/pac-discover.sh` (or the `.ps1`) creates a `pac auth`
profile and lists environments so you can copy the URL into `config.json`. `pac` cannot hand its
token to other tools, so the documentor authenticates on its own via MSAL using the same app
registration you use for `pac auth create --applicationId …`.

## Command-line options

```
--config, -c PATH          config file (default: config.local.json / config.json / configf.json)
--app, -a NAME             app display or unique name; repeatable; overrides config "apps"
--list-apps                list model-driven apps and exit
--whoami                   WhoAmI connection test
--output-dir, -o DIR       output directory
--output-file NAME         file name pattern; {app} and {timestamp} placeholders
--depth N                  traversal depth (0 = app components + sitemap only; 1 default; 2+ walks discovered entities)
--attributes form|all|none which attributes to list (fields on identified forms by default)
--include-relationships    list every relationship of walked entities and the entities on the other side
--include-inactive-forms   include inactive forms
--json                     also write the JSON model
--separate-workbooks       one workbook per app
-v / -vv                   progress / every HTTP request
```

## How discovery works

See [PLAN.md](PLAN.md) for the full mapping of Dataverse artefacts to discovery sources and the
walk algorithm. In short: `appmodulecomponents` → root entities, sitemap, explicit forms / views /
charts / BPFs → parse every form of every root entity (respecting each entity's
*root component behaviour*) → follow subgrids, lookups, quick view forms, timelines, related
navigation, views and charts → list the discovered tables with the reason they were found.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

The tests exercise the XML parsers and run the whole walker against an in-memory fake Web API,
so they need no Dataverse connection.

## Assumptions and open questions

These are the calls I made where the brief left room; each is a config switch so you can change
your mind without code changes.

1. **Traversal depth** – Only the app's own entities (sitemap / app components) have their forms
   walked (`traversalDepth: 1`). Tables discovered from those forms are listed but their forms are
   not walked. Set `2` if you want the second ring too.
2. **Attributes** – "attributes" means the fields placed on the identified forms
   (`attributeScope: "form"`). `"all"` lists every column of every discovered table (large);
   `"none"` skips attributes.
3. **Which forms** – Active Main, Quick View, Quick Create, Card and Main-Interactive forms
   (`formTypes: [2,6,7,11,12]`). For entities added to the app with *"Do not include
   subcomponents"*, only the forms/views/charts explicitly added to the app are used.
4. **Timeline** – Every activity table in the environment (plus Activity and Note) is attributed
   to a timeline, because timeline module configuration in form XML is not reliably parseable.
   Set `timelineIncludeAllActivityEntities: false` to only keep activity names that literally
   appear in the timeline's XML.
5. **System lookups** – Owner, Currency and similar lookups on forms *are* followed, so User, Team
   and Currency will appear as `Lookup Field` discoveries. Add their attribute names to
   `ignoreLookupAttributes` (e.g. `["ownerid","transactioncurrencyid"]`) to suppress them.
6. **Entity relationships** – Only relationships surfaced on forms (subgrids, related navigation)
   are followed by default. `includeAllRelationships: true` lists every 1:N / N:1 / N:N
   relationship of walked entities, which for Account/Contact is hundreds of rows.
7. **Views** – All active views of walked entities that are visible in apps (public, subgrid,
   quick find, lookup) are listed; Advanced Find / reporting / Outlook internals are skipped.
8. **Auth** – Client-credentials with a secret is the default. The `configf.json` name in the
   brief was read as a typo for `config.json`; both names are accepted.
9. **Multiple apps** – One workbook with two tabs per app; `--separate-workbooks` for one file each.
