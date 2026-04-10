"""
XSOAR REST API client.
All HTTP calls are centralized here.
"""

import os
import httpx
from typing import Any


class XSOARClient:
    def __init__(self):
        self.base_url = os.environ.get("XSOAR_URL", "").rstrip("/")
        self.api_key = os.environ.get("XSOAR_API_KEY", "")
        self.verify_ssl = os.environ.get("XSOAR_VERIFY_SSL", "true").lower() == "true"

        if not self.base_url or not self.api_key:
            raise ValueError("XSOAR_URL and XSOAR_API_KEY must be set in environment.")

    def _headers(self) -> dict:
        return {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-xdr-auth-id": "1",  # required for XSOAR v6
        }

    def request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        with httpx.Client(verify=self.verify_ssl, timeout=30.0) as client:
            resp = client.request(method, url, headers=self._headers(), **kwargs)
            resp.raise_for_status()
            return resp.json() if resp.content else {}

    # ── Incident ─────────────────────────────────────────────────────────────

    def search_incidents(self, query="", size=20, page=0) -> dict:
        body = {"filter": {"query": query, "size": size, "page": page,
                           "sort": [{"field": "occurred", "asc": False}]}}
        return self.request("POST", "/xsoar/incidents/search", json=body)

    def get_incident(self, incident_id: str) -> dict:
        return self.request("GET", f"/xsoar/incident/{incident_id}")

    def create_incident(self, name: str, type: str = "Unclassified",
                        severity: int = 1, details: str = "",
                        owner: str = "", playbook_id: str = "") -> dict:
        body = {"name": name, "type": type, "severity": severity, "details": details}
        if owner:
            body["owner"] = owner
        if playbook_id:
            body["playbookId"] = playbook_id
        return self.request("POST", "/xsoar/incident", json=body)

    def update_incident(self, incident_id: str, **fields) -> dict:
        body = {"id": incident_id, "version": -1, **fields}
        return self.request("PUT", f"/xsoar/incident/{incident_id}", json=body)

    def close_incident(self, incident_id: str, close_reason="Resolved",
                       close_notes="") -> dict:
        return self.request("POST", "/xsoar/incident/close", json={
            "id": incident_id, "status": 2,
            "closeReason": close_reason, "closeNotes": close_notes,
        })

    # ── War Room ──────────────────────────────────────────────────────────────

    def add_entry(self, incident_id: str, content: str) -> dict:
        return self.request("POST", "/xsoar/entry/execute", json={
            "id": incident_id, "content": content,
            "entryType": 1, "format": "markdown",
        })

    def get_entries(self, incident_id: str, page_size=50) -> dict:
        return self.request("POST", "/xsoar/investigation/entries",
                            json={"id": incident_id, "pageSize": page_size})

    # ── Playbook ──────────────────────────────────────────────────────────────

    def list_playbooks(self) -> list:
        result = self.request("GET", "/xsoar/playbook/search")
        return result.get("playbooks") or (result if isinstance(result, list) else [])

    def run_playbook(self, incident_id: str, playbook_id: str) -> dict:
        return self.request(
            "POST", f"/xsoar/incident/playbookrun/{incident_id}/{playbook_id}",
            json={"incidentId": incident_id, "version": -1},
        )

    # ── Indicator ─────────────────────────────────────────────────────────────

    def search_indicators(self, query="", ioc_type="", size=20) -> dict:
        body: dict = {"query": query, "size": size, "page": 0}
        if ioc_type:
            body["type"] = ioc_type
        return self.request("POST", "/xsoar/indicators/search", json=body)

    # ── Other ─────────────────────────────────────────────────────────────────

    def server_info(self) -> dict:
        return self.request("GET", "/xsoar/about")

    def list_users(self) -> list:
        result = self.request("GET", "/xsoar/user/list")
        return result if isinstance(result, list) else result.get("users", [])
