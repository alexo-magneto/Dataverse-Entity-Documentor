"""Token acquisition via MSAL (app-only, certificate, interactive, device code) or a raw token."""

from __future__ import annotations

import atexit
import logging
import os
import time
from pathlib import Path
from typing import Callable

from .config import AuthConfig

log = logging.getLogger(__name__)

# Microsoft's well-known public sample client id (has http://localhost registered).
# Only used when the user picks interactive/deviceCode and leaves clientId empty.
FALLBACK_PUBLIC_CLIENT_ID = "51f81489-12ee-4a9e-aaae-a2591f45987d"


def _authority(cfg: AuthConfig) -> str:
    if cfg.authority:
        return cfg.authority
    tenant = cfg.tenant_id or "organizations"
    return f"https://login.microsoftonline.com/{tenant}"


def _cache_path(cfg: AuthConfig) -> Path:
    if cfg.token_cache_path:
        return Path(cfg.token_cache_path).expanduser()
    return Path.home() / ".dataverse-app-documentor" / "token_cache.bin"


def build_token_provider(cfg: AuthConfig, environment_url: str) -> Callable[[], str]:
    """Return a zero-arg callable that yields a valid bearer token for the environment."""
    mode = (cfg.mode or "clientCredentials").strip()
    scopes = [f"{environment_url}/.default"]

    if mode == "accessToken":
        token = os.environ.get("DATAVERSE_ACCESS_TOKEN", "").strip()
        if not token:
            raise RuntimeError("DATAVERSE_ACCESS_TOKEN is not set.")
        return lambda: token

    import msal  # imported lazily so parsers/tests do not need it

    if mode in {"clientCredentials", "clientCertificate"}:
        if mode == "clientCredentials":
            credential: object = cfg.client_secret
        else:
            pem = Path(cfg.certificate_path).expanduser().read_text(encoding="utf-8")
            credential = {"private_key": pem, "thumbprint": cfg.certificate_thumbprint}
            if cfg.certificate_password:
                credential["passphrase"] = cfg.certificate_password
        app = msal.ConfidentialClientApplication(
            cfg.client_id, authority=_authority(cfg), client_credential=credential
        )
        state = {"token": None, "expires": 0.0}

        def provider() -> str:
            if state["token"] and time.time() < state["expires"] - 120:
                return state["token"]
            result = app.acquire_token_for_client(scopes=scopes)
            if "access_token" not in result:
                raise RuntimeError(f"Token acquisition failed: {result.get('error')}: {result.get('error_description')}")
            state["token"] = result["access_token"]
            state["expires"] = time.time() + int(result.get("expires_in", 3600))
            log.debug("Acquired app-only token (expires in %ss)", result.get("expires_in"))
            return state["token"]

        return provider

    if mode in {"interactive", "deviceCode"}:
        client_id = cfg.client_id or FALLBACK_PUBLIC_CLIENT_ID
        cache = msal.SerializableTokenCache()
        cache_file = _cache_path(cfg)
        if cache_file.exists():
            try:
                cache.deserialize(cache_file.read_text(encoding="utf-8"))
            except Exception:  # corrupt cache - start fresh
                pass

        def persist() -> None:
            if cache.has_state_changed:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(cache.serialize(), encoding="utf-8")
                try:
                    os.chmod(cache_file, 0o600)
                except OSError:
                    pass

        atexit.register(persist)
        app = msal.PublicClientApplication(client_id, authority=_authority(cfg), token_cache=cache)

        def provider() -> str:
            accounts = app.get_accounts()
            result = app.acquire_token_silent(scopes, account=accounts[0]) if accounts else None
            if not result:
                if mode == "interactive":
                    result = app.acquire_token_interactive(scopes=scopes)
                else:
                    flow = app.initiate_device_flow(scopes=scopes)
                    if "user_code" not in flow:
                        raise RuntimeError(f"Device flow failed: {flow}")
                    print(flow["message"], flush=True)
                    result = app.acquire_token_by_device_flow(flow)
                persist()
            if "access_token" not in result:
                raise RuntimeError(f"Token acquisition failed: {result.get('error')}: {result.get('error_description')}")
            return result["access_token"]

        return provider

    raise RuntimeError(f"Unsupported auth mode: {mode}")
