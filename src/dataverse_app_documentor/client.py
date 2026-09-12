"""Thin Dataverse Web API client with paging, retry and id-batch helpers."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Iterable

import requests

log = logging.getLogger(__name__)


def odata_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class DataverseError(RuntimeError):
    pass


class DataverseClient:
    def __init__(
        self,
        environment_url: str,
        token_provider: Callable[[], str],
        api_version: str = "v9.2",
        page_size: int = 5000,
        timeout: int = 180,
        max_retries: int = 6,
    ) -> None:
        self.environment_url = environment_url.rstrip("/")
        self.base_url = f"{self.environment_url}/api/data/{api_version}/"
        self._token_provider = token_provider
        self.page_size = page_size
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
        self.request_count = 0

    # ------------------------------------------------------------------ core
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token_provider()}",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "Prefer": f"odata.maxpagesize={self.page_size}",
        }

    def _request(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        attempt = 0
        while True:
            attempt += 1
            self.request_count += 1
            log.debug("GET %s %s", url, params or "")
            try:
                resp = self._session.get(url, headers=self._headers(), params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt > self.max_retries:
                    raise DataverseError(f"Request failed after {attempt} attempts: {exc}") from exc
                time.sleep(min(2 ** attempt, 30))
                continue
            if resp.status_code in (429, 500, 502, 503, 504) and attempt <= self.max_retries:
                wait = resp.headers.get("Retry-After")
                delay = float(wait) if wait and wait.isdigit() else min(2 ** attempt, 60)
                log.warning("HTTP %s from Dataverse, retrying in %.0fs (attempt %s)", resp.status_code, delay, attempt)
                time.sleep(delay)
                continue
            if resp.status_code >= 400:
                detail = ""
                try:
                    detail = resp.json().get("error", {}).get("message", "")
                except Exception:
                    detail = resp.text[:500]
                raise DataverseError(f"HTTP {resp.status_code} for {url}: {detail}")
            if not resp.content:
                return {}
            return resp.json()

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = path if path.startswith("http") else self.base_url + path
        return self._request(url, params)

    def get_all(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """GET a collection and follow @odata.nextLink until exhausted."""
        url = path if path.startswith("http") else self.base_url + path
        rows: list[dict[str, Any]] = []
        data = self._request(url, params)
        rows.extend(data.get("value", []))
        next_link = data.get("@odata.nextLink")
        while next_link:
            data = self._request(next_link)
            rows.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")
        return rows

    # --------------------------------------------------------------- helpers
    def get_by_id(self, entity_set: str, record_id: str, select: str) -> dict[str, Any] | None:
        try:
            return self.get(f"{entity_set}({record_id})", {"$select": select})
        except DataverseError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise

    def get_many_by_ids(
        self, entity_set: str, id_attribute: str, ids: Iterable[str], select: str, chunk: int = 20
    ) -> list[dict[str, Any]]:
        ids = [i for i in dict.fromkeys(ids) if i]
        rows: list[dict[str, Any]] = []
        for start in range(0, len(ids), chunk):
            batch = ids[start : start + chunk]
            flt = " or ".join(f"{id_attribute} eq {i}" for i in batch)
            rows.extend(self.get_all(entity_set, {"$select": select, "$filter": flt}))
        return rows

    def who_am_i(self) -> dict[str, Any]:
        return self.get("WhoAmI")
