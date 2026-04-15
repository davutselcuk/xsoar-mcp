"""
XSOAR REST API client.

All HTTP calls are centralized here. Features:
- Connection pooling via a reusable httpx.Client
- Debug logging (XSOAR_DEBUG=true)
- Retry on transient errors (5xx, 429, network errors)
- Context-manager support
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger("xsoar_mcp.client")

# Tunables
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5  # seconds
_DEFAULT_TIMEOUT = 30.0


class XSOARError(Exception):
    """Raised when XSOAR returns a non-retryable error."""


class XSOARClient:
    """XSOAR REST API client with connection pooling and retry."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        verify_ssl: bool | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = (base_url or os.environ.get("XSOAR_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("XSOAR_API_KEY", "")

        if verify_ssl is None:
            verify_ssl = os.environ.get("XSOAR_VERIFY_SSL", "true").lower() == "true"
        self.verify_ssl = verify_ssl

        if not self.base_url or not self.api_key:
            raise ValueError("XSOAR_URL and XSOAR_API_KEY must be set.")

        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self._headers(),
            verify=self.verify_ssl,
            timeout=timeout,
        )

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> XSOARClient:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-xdr-auth-id": "1",  # required for XSOAR v6
        }

    # ── core request with retry ────────────────────────────────────────────────

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Send an HTTP request with retry on transient failures."""
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                logger.debug("%s %s attempt=%d", method, path, attempt + 1)
                resp = self._client.request(method, path, **kwargs)

                # Retry 5xx/429, fail-fast on 4xx
                if resp.status_code >= 500 or resp.status_code == 429:
                    if attempt < _MAX_RETRIES - 1:
                        backoff = _BACKOFF_BASE * (2**attempt)
                        logger.warning(
                            "HTTP %d on %s %s, retrying in %.1fs",
                            resp.status_code, method, path, backoff,
                        )
                        time.sleep(backoff)
                        continue
                resp.raise_for_status()
                return resp.json() if resp.content else {}

            except httpx.HTTPStatusError as e:
                # 4xx: surface a helpful message
                body = (e.response.text or "")[:500]
                raise XSOARError(
                    f"XSOAR HTTP {e.response.status_code} on {method} {path}: {body}"
                ) from e

            except (httpx.TransportError, httpx.TimeoutException) as e:
                last_exc = e
                if attempt < _MAX_RETRIES - 1:
                    backoff = _BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        "Network error on %s %s: %s — retrying in %.1fs",
                        method, path, e, backoff,
                    )
                    time.sleep(backoff)
                    continue
                break

        raise XSOARError(f"XSOAR request failed after {_MAX_RETRIES} attempts: {last_exc}")

    # ── Incident ──────────────────────────────────────────────────────────────

    def search_incidents(self, query: str = "", size: int = 20, page: int = 0,
                         sort_field: str = "occurred", sort_asc: bool = False) -> dict:
        body = {
            "filter": {
                "query": query, "size": size, "page": page,
                "sort": [{"field": sort_field, "asc": sort_asc}],
            }
        }
        return self.request("POST", "/xsoar/incidents/search", json=body)

    def get_incident(self, incident_id: str) -> dict:
        return self.request("GET", f"/xsoar/incident/{incident_id}")

    def create_incident(self, name: str, type: str = "Unclassified",
                        severity: int = 1, details: str = "",
                        owner: str = "", playbook_id: str = "",
                        labels: list[dict] | None = None) -> dict:
        body: dict = {"name": name, "type": type, "severity": severity, "details": details}
        if owner:
            body["owner"] = owner
        if playbook_id:
            body["playbookId"] = playbook_id
        if labels:
            body["labels"] = labels
        return self.request("POST", "/xsoar/incident", json=body)

    def update_incident(self, incident_id: str, **fields: Any) -> dict:
        body = {"id": incident_id, "version": -1, **fields}
        return self.request("PUT", f"/xsoar/incident/{incident_id}", json=body)

    def close_incident(self, incident_id: str, close_reason: str = "Resolved",
                       close_notes: str = "") -> dict:
        return self.request("POST", "/xsoar/incident/close", json={
            "id": incident_id, "status": 2,
            "closeReason": close_reason, "closeNotes": close_notes,
        })

    def reopen_incident(self, incident_id: str) -> dict:
        """Reopen a previously closed incident (status -> Active)."""
        return self.request("POST", "/xsoar/incident/reopen", json={
            "id": incident_id, "status": 1,
        })

    # ── War Room ──────────────────────────────────────────────────────────────

    def add_entry(self, incident_id: str, content: str,
                  markdown: bool = True) -> dict:
        return self.request("POST", "/xsoar/entry/execute", json={
            "id": incident_id, "content": content, "entryType": 1,
            "format": "markdown" if markdown else "text",
        })

    def get_entries(self, incident_id: str, page_size: int = 50) -> dict:
        return self.request("POST", "/xsoar/investigation/entries",
                            json={"id": incident_id, "pageSize": page_size})

    def execute_command(self, incident_id: str, command: str) -> dict:
        """
        Run an integration command in an incident's War Room (synchronous).

        Args:
            incident_id: Target incident ID.
            command: Command text, starting with '!' — e.g. '!ip ip=8.8.8.8'.
        """
        if not command.startswith("!"):
            command = "!" + command
        return self.request("POST", "/xsoar/entry/execute/sync", json={
            "investigationId": incident_id, "data": command,
        })

    # ── Playbook ──────────────────────────────────────────────────────────────

    def list_playbooks(self, query: str = "") -> list:
        params = {"query": query} if query else {}
        result = self.request("GET", "/xsoar/playbook/search", params=params)
        return result.get("playbooks") or (result if isinstance(result, list) else [])

    def run_playbook(self, incident_id: str, playbook_id: str) -> dict:
        return self.request(
            "POST", f"/xsoar/incident/playbookrun/{incident_id}/{playbook_id}",
            json={"incidentId": incident_id, "version": -1},
        )

    def get_work_plan(self, incident_id: str) -> dict:
        """Get playbook task status (work plan) for an incident."""
        return self.request("GET", f"/xsoar/inv-playbook/{incident_id}")

    # ── Indicator ─────────────────────────────────────────────────────────────

    def search_indicators(self, query: str = "", ioc_type: str = "",
                          size: int = 20, page: int = 0) -> dict:
        body: dict = {"query": query, "size": size, "page": page}
        if ioc_type:
            body["type"] = ioc_type
        return self.request("POST", "/xsoar/indicators/search", json=body)

    def create_indicator(self, value: str, indicator_type: str = "IP",
                         score: int = 0, comment: str = "",
                         source: str = "mcp") -> dict:
        """Create a new threat indicator."""
        body = {
            "indicator": {
                "value": value,
                "indicator_type": indicator_type,
                "score": score,
                "comment": comment,
                "source": source,
            }
        }
        return self.request("POST", "/xsoar/indicator/create", json=body)

    def delete_indicator(self, indicator_id: str) -> dict:
        return self.request("POST", "/xsoar/indicator/batchDelete", json={
            "ids": [indicator_id], "DONOTWHITELIST": False,
        })

    # ── Integration ───────────────────────────────────────────────────────────

    def list_integrations(self, query: str = "") -> dict:
        params = {"query": query} if query else {}
        return self.request("GET", "/xsoar/settings/integration/search",
                            params=params)

    # ── Other ─────────────────────────────────────────────────────────────────

    def server_info(self) -> dict:
        return self.request("GET", "/xsoar/about")

    def list_users(self) -> list:
        result = self.request("GET", "/xsoar/user/list")
        return result if isinstance(result, list) else result.get("users", [])

    def list_incident_types(self) -> list:
        result = self.request("POST", "/xsoar/incidenttype/search", json={"size": 500})
        return result.get("incidentTypes") or (result if isinstance(result, list) else [])

    def list_incident_fields(self) -> list:
        result = self.request("GET", "/xsoar/incidentfields")
        return result if isinstance(result, list) else []
