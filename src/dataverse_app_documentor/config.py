"""Configuration loading (config.json + environment variable overrides)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_FILES = ("config.local.json", "config.json", "configf.json")

# Form types (systemform.type) that are walked by default. Dashboards (0/10/13)
# are always processed when they are referenced by the app or its sitemap.
DEFAULT_FORM_TYPES = [2, 6, 7, 11, 12]


@dataclass
class AuthConfig:
    mode: str = "clientCredentials"  # clientCredentials | clientCertificate | interactive | deviceCode | accessToken
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    certificate_path: str = ""
    certificate_thumbprint: str = ""
    certificate_password: str = ""
    authority: str = ""  # optional override, e.g. https://login.microsoftonline.us/<tenant>
    token_cache_path: str = ""


@dataclass
class OutputConfig:
    directory: str = "./output"
    file_name: str = "{app}-app-components-{timestamp}.xlsx"
    single_workbook: bool = True
    write_json: bool = False


@dataclass
class DiscoveryConfig:
    traversal_depth: int = 1
    form_types: list[int] = field(default_factory=lambda: list(DEFAULT_FORM_TYPES))
    include_inactive_forms: bool = False
    attribute_scope: str = "form"  # form | all | none
    include_all_relationships: bool = False
    timeline_include_all_activity_entities: bool = True
    include_views: bool = True
    include_charts: bool = True
    ignore_lookup_attributes: list[str] = field(default_factory=list)
    exclude_entities: list[str] = field(default_factory=list)


@dataclass
class AppConfig:
    environment_url: str = ""
    api_version: str = "v9.2"
    apps: list[str] = field(default_factory=list)
    auth: AuthConfig = field(default_factory=AuthConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    source_path: str = ""


def _camel_to_snake(name: str) -> str:
    out = []
    for ch in name:
        if ch.isupper():
            out.append("_")
            out.append(ch.lower())
        else:
            out.append(ch)
    return "".join(out).lstrip("_")


def _apply(section: Any, values: dict[str, Any]) -> None:
    for key, value in values.items():
        attr = _camel_to_snake(key)
        if hasattr(section, attr):
            setattr(section, attr, value)


def find_config_file(explicit: str | None = None, start: Path | None = None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    base = start or Path.cwd()
    for name in DEFAULT_CONFIG_FILES:
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


def load_config(path: str | None = None) -> AppConfig:
    """Load config.json (or the first default file found) and apply env overrides."""
    cfg = AppConfig()
    found = find_config_file(path)
    if found:
        raw = json.loads(found.read_text(encoding="utf-8-sig"))
        cfg.source_path = str(found)
        cfg.environment_url = raw.get("environmentUrl", cfg.environment_url)
        cfg.api_version = raw.get("apiVersion", cfg.api_version)
        apps = raw.get("apps", [])
        if isinstance(apps, str):
            apps = [apps]
        cfg.apps = list(apps)
        _apply(cfg.auth, raw.get("auth", {}) or {})
        _apply(cfg.output, raw.get("output", {}) or {})
        _apply(cfg.discovery, raw.get("discovery", {}) or {})
    elif path:
        raise FileNotFoundError(f"Config file not found: {path}")

    # Environment variable overrides (never commit secrets to config.json).
    env = os.environ
    cfg.environment_url = env.get("DATAVERSE_URL", cfg.environment_url)
    cfg.auth.tenant_id = env.get("DATAVERSE_TENANT_ID", cfg.auth.tenant_id)
    cfg.auth.client_id = env.get("DATAVERSE_CLIENT_ID", cfg.auth.client_id)
    cfg.auth.client_secret = env.get("DATAVERSE_CLIENT_SECRET", cfg.auth.client_secret)
    if env.get("DATAVERSE_ACCESS_TOKEN"):
        cfg.auth.mode = "accessToken"
    if env.get("DATAVERSE_AUTH_MODE"):
        cfg.auth.mode = env["DATAVERSE_AUTH_MODE"]

    cfg.environment_url = (cfg.environment_url or "").strip().rstrip("/")
    return cfg


def validate_config(cfg: AppConfig) -> list[str]:
    problems: list[str] = []
    if not cfg.environment_url or "yourorg" in cfg.environment_url.lower():
        problems.append("environmentUrl is not set (e.g. https://contoso.crm.dynamics.com).")
    mode = (cfg.auth.mode or "").strip()
    if mode not in {"clientCredentials", "clientCertificate", "interactive", "deviceCode", "accessToken"}:
        problems.append(f"auth.mode '{mode}' is not supported.")
    if mode in {"clientCredentials", "clientCertificate", "interactive", "deviceCode"} and not cfg.auth.client_id:
        problems.append("auth.clientId is required for this auth mode.")
    if mode in {"clientCredentials", "clientCertificate"} and not cfg.auth.tenant_id:
        problems.append("auth.tenantId is required for app-only authentication.")
    if mode == "clientCredentials" and not cfg.auth.client_secret:
        problems.append("auth.clientSecret (or env DATAVERSE_CLIENT_SECRET) is required for clientCredentials.")
    if mode == "clientCertificate" and not cfg.auth.certificate_path:
        problems.append("auth.certificatePath is required for clientCertificate.")
    if mode == "accessToken" and not os.environ.get("DATAVERSE_ACCESS_TOKEN"):
        problems.append("auth.mode is accessToken but env DATAVERSE_ACCESS_TOKEN is empty.")
    if cfg.discovery.attribute_scope not in {"form", "all", "none"}:
        problems.append("discovery.attributeScope must be one of: form, all, none.")
    return problems
