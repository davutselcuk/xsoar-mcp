"""
XSOAR MCP Server
Wraps the Palo Alto Cortex XSOAR REST API as MCP tools.
Compatible with XSOAR v6.x.
"""

import os
from typing import Any
from mcp.server.fastmcp import FastMCP

from .client import XSOARClient

# ── Configuration ─────────────────────────────────────────────────────────────
XSOAR_URL = os.environ.get("XSOAR_URL", "").rstrip("/")
XSOAR_API_KEY = os.environ.get("XSOAR_API_KEY", "")
XSOAR_VERIFY_SSL = os.environ.get("XSOAR_VERIFY_SSL", "true").lower() == "true"

# ── MCP Server ────────────────────────────────────────────────────────────────
mcp = FastMCP(
    name="xsoar",
    instructions=(
        "Tools for interacting with Palo Alto Cortex XSOAR SOAR platform. "
        "Incident management, playbook execution, indicator search, and more."
    ),
)

import httpx


def _client() -> httpx.Client:
    """Returns an authenticated XSOAR HTTP client."""
    if not XSOAR_URL or not XSOAR_API_KEY:
        raise ValueError(
            "XSOAR_URL and XSOAR_API_KEY environment variables must be set."
        )
    return httpx.Client(
        base_url=XSOAR_URL,
        headers={
            "Authorization": XSOAR_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-xdr-auth-id": "1",  # required for XSOAR v6
        },
        verify=XSOAR_VERIFY_SSL,
        timeout=30.0,
    )


def _req(method: str, path: str, **kwargs) -> Any:
    """Makes an HTTP request; raises on error."""
    with _client() as c:
        resp = c.request(method, path, **kwargs)
        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return {"status": "ok"}


# ── INCIDENT TOOLS ────────────────────────────────────────────────────────────

@mcp.tool()
def search_incidents(
    query: str = "",
    size: int = 20,
    page: int = 0,
    sort_field: str = "occurred",
    sort_order: str = "desc",
) -> dict:
    """
    Search XSOAR incidents.

    Args:
        query: Lucene/Elasticsearch query string. Example: 'type:Phishing AND severity:3'
        size: Maximum number of incidents to return (default: 20)
        page: Page number (default: 0)
        sort_field: Field to sort by (default: occurred)
        sort_order: Sort direction - 'asc' or 'desc'
    """
    body = {
        "filter": {
            "query": query,
            "size": size,
            "page": page,
            "sort": [{"field": sort_field, "asc": sort_order == "asc"}],
        }
    }
    result = _req("POST", "/xsoar/incidents/search", json=body)
    incidents = result.get("data") or []
    total = result.get("total", len(incidents))
    return {
        "total": total,
        "returned": len(incidents),
        "incidents": [_fmt_incident(i) for i in incidents],
    }


@mcp.tool()
def get_incident(incident_id: str) -> dict:
    """
    Get details of a specific incident.

    Args:
        incident_id: XSOAR incident ID
    """
    result = _req("GET", f"/xsoar/incident/{incident_id}")
    return _fmt_incident(result)


@mcp.tool()
def create_incident(
    name: str,
    type: str = "Unclassified",
    severity: int = 1,
    details: str = "",
    labels: list[dict] | None = None,
    owner: str = "",
    playbookId: str = "",
) -> dict:
    """
    Create a new XSOAR incident.

    Args:
        name: Incident name (required)
        type: Incident type (e.g. 'Phishing', 'Malware', 'Unclassified')
        severity: Severity level 0=Unknown, 1=Low, 2=Medium, 3=High, 4=Critical
        details: Incident description
        labels: Label list, e.g. [{"type": "Category", "value": "Test"}]
        owner: Responsible username
        playbookId: Playbook ID to auto-start
    """
    body: dict = {
        "name": name,
        "type": type,
        "severity": severity,
        "details": details,
    }
    if labels:
        body["labels"] = labels
    if owner:
        body["owner"] = owner
    if playbookId:
        body["playbookId"] = playbookId

    result = _req("POST", "/xsoar/incident", json=body)
    return {"created": True, "id": result.get("id"), "name": result.get("name")}


@mcp.tool()
def update_incident(
    incident_id: str,
    severity: int | None = None,
    owner: str | None = None,
    status: int | None = None,
    details: str | None = None,
    custom_fields: dict | None = None,
) -> dict:
    """
    Update an existing incident.

    Args:
        incident_id: ID of the incident to update
        severity: New severity (0-4)
        owner: New assigned user
        status: Status code (0=Pending, 1=Active, 2=Closed, 3=Archived)
        details: New description
        custom_fields: Custom fields dict, e.g. {"customField": "value"}
    """
    body: dict = {"id": incident_id, "version": -1}
    if severity is not None:
        body["severity"] = severity
    if owner is not None:
        body["owner"] = owner
    if status is not None:
        body["status"] = status
    if details is not None:
        body["details"] = details
    if custom_fields:
        body["CustomFields"] = custom_fields

    _req("PUT", f"/xsoar/incident/{incident_id}", json=body)
    return {"updated": True, "id": incident_id}


@mcp.tool()
def close_incident(
    incident_id: str,
    close_reason: str = "Resolved",
    close_notes: str = "",
) -> dict:
    """
    Close an incident.

    Args:
        incident_id: ID of the incident to close
        close_reason: Reason for closing (Resolved, False Positive, Duplicate, etc.)
        close_notes: Closing notes
    """
    body = {
        "id": incident_id,
        "status": 2,  # Closed
        "closeReason": close_reason,
        "closeNotes": close_notes,
    }
    _req("POST", "/xsoar/incident/close", json=body)
    return {"closed": True, "id": incident_id}


# ── WAR ROOM TOOLS ────────────────────────────────────────────────────────────

@mcp.tool()
def add_war_room_entry(
    incident_id: str,
    content: str,
    markdown: bool = True,
) -> dict:
    """
    Add a note or comment to an incident's War Room.

    Args:
        incident_id: Target incident ID
        content: Content to add (supports Markdown)
        markdown: Whether to render content as Markdown
    """
    body = {
        "id": incident_id,
        "content": content,
        "entryType": 1,  # Note
        "format": "markdown" if markdown else "text",
    }
    _req("POST", "/xsoar/entry/execute", json=body)
    return {"entry_added": True, "incident_id": incident_id}


@mcp.tool()
def get_war_room_entries(incident_id: str, max_entries: int = 50) -> dict:
    """
    Get War Room entries (notes, commands, results) for an incident.

    Args:
        incident_id: Incident ID
        max_entries: Maximum number of entries to return
    """
    body = {"id": incident_id, "pageSize": max_entries}
    result = _req("POST", "/xsoar/investigation/entries", json=body)
    entries = result.get("entries") or []
    return {
        "incident_id": incident_id,
        "entry_count": len(entries),
        "entries": [
            {
                "id": e.get("id"),
                "type": e.get("type"),
                "created": e.get("created"),
                "user": e.get("user"),
                "content": (e.get("contents") or "")[:500],
            }
            for e in entries
        ],
    }


# ── PLAYBOOK TOOLS ────────────────────────────────────────────────────────────

@mcp.tool()
def list_playbooks(search: str = "") -> dict:
    """
    List available playbooks.

    Args:
        search: Filter by playbook name (empty returns all)
    """
    result = _req("GET", "/xsoar/playbook/search", params={"query": search} if search else {})
    playbooks = result.get("playbooks") or result if isinstance(result, list) else []
    return {
        "count": len(playbooks),
        "playbooks": [
            {"id": p.get("id"), "name": p.get("name"), "description": p.get("description", "")}
            for p in playbooks
        ],
    }


@mcp.tool()
def run_playbook_on_incident(incident_id: str, playbook_id: str) -> dict:
    """
    Run a playbook on an incident.

    Args:
        incident_id: Target incident ID
        playbook_id: ID of the playbook to run
    """
    body = {"incidentId": incident_id, "version": -1}
    _req("POST", f"/xsoar/incident/playbookrun/{incident_id}/{playbook_id}", json=body)
    return {"playbook_started": True, "incident_id": incident_id, "playbook_id": playbook_id}


# ── INDICATOR (IOC) TOOLS ─────────────────────────────────────────────────────

@mcp.tool()
def search_indicators(
    query: str = "",
    indicator_type: str = "",
    size: int = 20,
) -> dict:
    """
    Search threat indicators (IOCs): IPs, domains, hashes, URLs, etc.

    Args:
        query: Search query (e.g. '8.8.8.8' or 'malware.example.com')
        indicator_type: Type filter (IP, Domain, File, URL, CVE, etc.)
        size: Maximum number of results
    """
    body: dict = {"query": query, "size": size, "page": 0}
    if indicator_type:
        body["type"] = indicator_type

    result = _req("POST", "/xsoar/indicators/search", json=body)
    indicators = result.get("iocObjects") or []
    return {
        "total": result.get("total", len(indicators)),
        "returned": len(indicators),
        "indicators": [
            {
                "id": ind.get("id"),
                "value": ind.get("value"),
                "type": ind.get("indicator_type"),
                "score": ind.get("score"),  # 0=Unknown, 1=Good, 2=Suspicious, 3=Bad
                "expiration": ind.get("expiration"),
                "comment": ind.get("comment", ""),
            }
            for ind in indicators
        ],
    }


@mcp.tool()
def get_indicator(indicator_value: str) -> dict:
    """
    Get full details of a specific indicator (IOC).

    Args:
        indicator_value: Indicator value (IP address, domain, MD5 hash, etc.)
    """
    result = _req("POST", "/xsoar/indicators/search", json={"query": indicator_value, "size": 1})
    items = result.get("iocObjects") or []
    if not items:
        return {"found": False, "value": indicator_value}
    ind = items[0]
    return {
        "found": True,
        "id": ind.get("id"),
        "value": ind.get("value"),
        "type": ind.get("indicator_type"),
        "score": ind.get("score"),
        "created": ind.get("timestamp"),
        "modified": ind.get("modified"),
        "expiration": ind.get("expiration"),
        "comment": ind.get("comment", ""),
        "custom_fields": ind.get("CustomFields", {}),
        "related_incidents": ind.get("relatedIncCount", 0),
    }


# ── SERVER STATUS ─────────────────────────────────────────────────────────────

@mcp.tool()
def get_server_info() -> dict:
    """
    Check XSOAR server version and connectivity.
    Use this to verify the connection is working.
    """
    result = _req("GET", "/xsoar/about")
    return {
        "connected": True,
        "version": result.get("demistoVersion"),
        "build": result.get("buildNum"),
        "platform": result.get("platform"),
    }


@mcp.tool()
def list_users() -> dict:
    """
    List XSOAR users. Useful for incident assignment.
    """
    result = _req("GET", "/xsoar/user/list")
    users = result if isinstance(result, list) else result.get("users", [])
    return {
        "count": len(users),
        "users": [
            {"username": u.get("id"), "name": u.get("name"), "email": u.get("email", "")}
            for u in users
        ],
    }


# ── HELPERS ───────────────────────────────────────────────────────────────────

_SEVERITY = {0: "Unknown", 1: "Low", 2: "Medium", 3: "High", 4: "Critical"}
_STATUS = {0: "Pending", 1: "Active", 2: "Closed", 3: "Archived"}


def _fmt_incident(i: dict) -> dict:
    """Convert a raw incident dict to a readable format."""
    return {
        "id": i.get("id"),
        "name": i.get("name"),
        "type": i.get("type"),
        "severity": _SEVERITY.get(i.get("severity", 0), str(i.get("severity"))),
        "severity_code": i.get("severity"),
        "status": _STATUS.get(i.get("status", 0), str(i.get("status"))),
        "owner": i.get("owner"),
        "occurred": i.get("occurred"),
        "created": i.get("created"),
        "modified": i.get("modified"),
        "closed": i.get("closed"),
        "close_reason": i.get("closeReason"),
        "details": (i.get("details") or "")[:300],
        "labels": i.get("labels", []),
        "playbook": i.get("playbookId"),
    }


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
