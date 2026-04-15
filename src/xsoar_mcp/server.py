"""
XSOAR MCP Server
Wraps the Palo Alto Cortex XSOAR REST API as MCP tools, resources, and prompts.
Compatible with XSOAR v6.x.

Environment variables:
  XSOAR_URL         - XSOAR server URL (required)
  XSOAR_API_KEY     - XSOAR API key (required)
  XSOAR_VERIFY_SSL  - SSL verification (default: true)
  XSOAR_READ_ONLY   - If 'true', disables write tools (default: false)
  XSOAR_DEBUG       - If 'true', enables debug logging (default: false)
"""

from __future__ import annotations

import json
import logging
import os

from mcp.server.fastmcp import FastMCP

from .client import XSOARClient, XSOARError
from .utils import SCORE_MAP, fmt_incident, fmt_indicator

# ── Configuration ─────────────────────────────────────────────────────────────

READ_ONLY = os.environ.get("XSOAR_READ_ONLY", "false").lower() == "true"
DEBUG = os.environ.get("XSOAR_DEBUG", "false").lower() == "true"

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("xsoar_mcp.server")

if READ_ONLY:
    logger.info("Running in READ-ONLY mode — write tools disabled.")

# ── MCP Server ────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="xsoar",
    instructions=(
        "Tools, resources, and prompts for Palo Alto Cortex XSOAR SOAR platform. "
        "Incident management, playbook execution, indicator search, integration "
        "commands, and more."
    ),
)

# Lazy singleton XSOARClient — reuses HTTP connections.
_client: XSOARClient | None = None


def _xsoar() -> XSOARClient:
    global _client
    if _client is None:
        _client = XSOARClient()
    return _client


def _readonly_guard(tool: str) -> dict | None:
    """If READ_ONLY is set, return an error dict; otherwise None."""
    if READ_ONLY:
        logger.warning("Blocked write tool '%s' in read-only mode", tool)
        return {
            "error": "read_only_mode",
            "message": (
                f"Tool '{tool}' is disabled because XSOAR_READ_ONLY=true. "
                "Unset XSOAR_READ_ONLY to enable write operations."
            ),
        }
    return None


# ═════════════════════════════════════════════════════════════════════════════
#   INCIDENT TOOLS
# ═════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def search_incidents(
    query: str = "",
    size: int = 20,
    page: int = 0,
    sort_field: str = "occurred",
    sort_order: str = "desc",
) -> dict:
    """
    Search XSOAR incidents using a Lucene query.

    Examples:
        query=""                                    # all recent
        query="type:Phishing AND severity:>=3"
        query="owner:analyst1 AND status:1"
        query='created:>="2024-01-01"'
        query="name:*ransomware*"

    Args:
        query: Lucene/Elasticsearch query string.
        size: Maximum number of incidents (default 20, max 500).
        page: Page number (0-based).
        sort_field: Field to sort by (default: occurred).
        sort_order: 'asc' or 'desc' (default: desc).
    """
    try:
        result = _xsoar().search_incidents(
            query=query, size=size, page=page,
            sort_field=sort_field, sort_asc=(sort_order == "asc"),
        )
    except XSOARError as e:
        return {"error": str(e)}

    incidents = result.get("data") or []
    return {
        "total": result.get("total", len(incidents)),
        "returned": len(incidents),
        "incidents": [fmt_incident(i) for i in incidents],
    }


@mcp.tool()
def get_incident(incident_id: str) -> dict:
    """Get full details of a specific incident by ID."""
    try:
        return fmt_incident(_xsoar().get_incident(incident_id))
    except XSOARError as e:
        return {"error": str(e)}


@mcp.tool()
def create_incident(
    name: str,
    type: str = "Unclassified",
    severity: int = 1,
    details: str = "",
    labels: list[dict] | None = None,
    owner: str = "",
    playbook_id: str = "",
) -> dict:
    """
    Create a new XSOAR incident.

    Args:
        name: Incident name (required).
        type: Incident type (e.g. 'Phishing', 'Malware').
        severity: 0=Unknown, 1=Low, 2=Medium, 3=High, 4=Critical.
        details: Description / body.
        labels: e.g. [{"type": "Category", "value": "Test"}].
        owner: Responsible username.
        playbook_id: Playbook ID to auto-start.
    """
    if (blocked := _readonly_guard("create_incident")):
        return blocked
    try:
        result = _xsoar().create_incident(
            name=name, type=type, severity=severity, details=details,
            owner=owner, playbook_id=playbook_id, labels=labels,
        )
    except XSOARError as e:
        return {"error": str(e)}
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
        incident_id: Incident ID.
        severity: 0-4.
        owner: Username.
        status: 0=Pending, 1=Active, 2=Closed, 3=Archived.
        details: New description.
        custom_fields: e.g. {"customField": "value"}.
    """
    if (blocked := _readonly_guard("update_incident")):
        return blocked

    fields: dict = {}
    if severity is not None:
        fields["severity"] = severity
    if owner is not None:
        fields["owner"] = owner
    if status is not None:
        fields["status"] = status
    if details is not None:
        fields["details"] = details
    if custom_fields:
        fields["CustomFields"] = custom_fields

    try:
        _xsoar().update_incident(incident_id, **fields)
    except XSOARError as e:
        return {"error": str(e)}
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
        incident_id: Incident ID.
        close_reason: e.g. 'Resolved', 'False Positive', 'Duplicate'.
        close_notes: Closing notes.
    """
    if (blocked := _readonly_guard("close_incident")):
        return blocked
    try:
        _xsoar().close_incident(incident_id, close_reason, close_notes)
    except XSOARError as e:
        return {"error": str(e)}
    return {"closed": True, "id": incident_id}


@mcp.tool()
def reopen_incident(incident_id: str) -> dict:
    """Reopen a previously closed incident (sets status to Active)."""
    if (blocked := _readonly_guard("reopen_incident")):
        return blocked
    try:
        _xsoar().reopen_incident(incident_id)
    except XSOARError as e:
        return {"error": str(e)}
    return {"reopened": True, "id": incident_id}


# ═════════════════════════════════════════════════════════════════════════════
#   WAR ROOM TOOLS
# ═════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def add_war_room_entry(
    incident_id: str,
    content: str,
    markdown: bool = True,
) -> dict:
    """Add a note/comment to an incident's War Room (supports Markdown)."""
    if (blocked := _readonly_guard("add_war_room_entry")):
        return blocked
    try:
        _xsoar().add_entry(incident_id, content, markdown=markdown)
    except XSOARError as e:
        return {"error": str(e)}
    return {"entry_added": True, "incident_id": incident_id}


@mcp.tool()
def get_war_room_entries(incident_id: str, max_entries: int = 50) -> dict:
    """Get War Room entries (notes, commands, results) for an incident."""
    try:
        result = _xsoar().get_entries(incident_id, page_size=max_entries)
    except XSOARError as e:
        return {"error": str(e)}

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


@mcp.tool()
def execute_integration_command(
    incident_id: str,
    command: str,
) -> dict:
    """
    Run an integration command synchronously in an incident's War Room.

    This is the core SOAR power: call any enabled integration command (threat
    intel lookups, firewall actions, EDR queries, etc.).

    Examples:
        command="!ip ip=8.8.8.8"
        command="!vt-file file=<sha256>"
        command="!panorama-block-ip ip=1.2.3.4 rule=block_rule"
        command="!xdr-get-endpoints endpoint_id_list=<id>"

    Args:
        incident_id: Target incident ID (creates War Room context).
        command: XSOAR command starting with '!' (leading '!' optional).
    """
    if (blocked := _readonly_guard("execute_integration_command")):
        return blocked
    try:
        result = _xsoar().execute_command(incident_id, command)
    except XSOARError as e:
        return {"error": str(e)}

    # Result is typically a list of entry objects
    entries = result if isinstance(result, list) else [result]
    return {
        "executed": True,
        "incident_id": incident_id,
        "command": command,
        "entry_count": len(entries),
        "results": [
            {
                "id": e.get("id"),
                "type": e.get("type"),
                "content": (e.get("contents") or str(e.get("entry", "")))[:800],
            }
            for e in entries[:5]  # cap to first 5 entries
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
#   PLAYBOOK TOOLS
# ═════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def list_playbooks(search: str = "") -> dict:
    """List available playbooks, optionally filtered by name."""
    try:
        playbooks = _xsoar().list_playbooks(query=search)
    except XSOARError as e:
        return {"error": str(e)}
    return {
        "count": len(playbooks),
        "playbooks": [
            {"id": p.get("id"), "name": p.get("name"),
             "description": p.get("description", "")}
            for p in playbooks
        ],
    }


@mcp.tool()
def run_playbook_on_incident(incident_id: str, playbook_id: str) -> dict:
    """Run a playbook on an incident."""
    if (blocked := _readonly_guard("run_playbook_on_incident")):
        return blocked
    try:
        _xsoar().run_playbook(incident_id, playbook_id)
    except XSOARError as e:
        return {"error": str(e)}
    return {"playbook_started": True, "incident_id": incident_id,
            "playbook_id": playbook_id}


@mcp.tool()
def get_incident_work_plan(incident_id: str) -> dict:
    """
    Get the playbook execution status (work plan) for an incident:
    which tasks have completed, are running, or are pending.
    """
    try:
        result = _xsoar().get_work_plan(incident_id)
    except XSOARError as e:
        return {"error": str(e)}

    tasks = result.get("tasks") or {}
    return {
        "incident_id": incident_id,
        "playbook_id": result.get("playbookId"),
        "state": result.get("state"),
        "task_count": len(tasks),
        "tasks": [
            {
                "id": t.get("id"),
                "name": (t.get("task") or {}).get("name"),
                "state": t.get("state"),
                "type": (t.get("task") or {}).get("type"),
                "started": t.get("startDate"),
                "completed": t.get("completedDate"),
            }
            for t in (tasks.values() if isinstance(tasks, dict) else tasks)
        ][:50],
    }


# ═════════════════════════════════════════════════════════════════════════════
#   INDICATOR (IOC) TOOLS
# ═════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def search_indicators(
    query: str = "",
    indicator_type: str = "",
    size: int = 20,
) -> dict:
    """
    Search threat indicators (IOCs).

    Examples:
        query="8.8.8.8"
        query="*.example.com", indicator_type="Domain"
        query="score:3", indicator_type="File"     # known bad hashes

    Args:
        query: Search value or expression.
        indicator_type: Optional type filter (IP, Domain, File, URL, CVE, Email).
        size: Max results (default 20).
    """
    try:
        result = _xsoar().search_indicators(
            query=query, ioc_type=indicator_type, size=size,
        )
    except XSOARError as e:
        return {"error": str(e)}

    indicators = result.get("iocObjects") or []
    return {
        "total": result.get("total", len(indicators)),
        "returned": len(indicators),
        "indicators": [fmt_indicator(ind) for ind in indicators],
    }


@mcp.tool()
def get_indicator(indicator_value: str) -> dict:
    """Get full details of a specific indicator (IOC) by value."""
    try:
        result = _xsoar().search_indicators(query=indicator_value, size=1)
    except XSOARError as e:
        return {"error": str(e)}

    items = result.get("iocObjects") or []
    if not items:
        return {"found": False, "value": indicator_value}
    return {"found": True, **fmt_indicator(items[0])}


@mcp.tool()
def create_indicator(
    value: str,
    indicator_type: str = "IP",
    score: int = 0,
    comment: str = "",
    source: str = "xsoar-mcp",
) -> dict:
    """
    Create a new threat indicator (IOC).

    Args:
        value: Indicator value (IP, hash, domain, etc.).
        indicator_type: 'IP', 'Domain', 'File', 'URL', 'CVE', 'Email', etc.
        score: 0=Unknown, 1=Good, 2=Suspicious, 3=Bad.
        comment: Free-text note.
        source: Source identifier.
    """
    if (blocked := _readonly_guard("create_indicator")):
        return blocked
    try:
        result = _xsoar().create_indicator(
            value=value, indicator_type=indicator_type,
            score=score, comment=comment, source=source,
        )
    except XSOARError as e:
        return {"error": str(e)}

    return {
        "created": True,
        "id": result.get("id") or (result.get("indicator") or {}).get("id"),
        "value": value,
        "type": indicator_type,
        "score": SCORE_MAP.get(score, str(score)),
    }


# ═════════════════════════════════════════════════════════════════════════════
#   INTEGRATION / METADATA TOOLS
# ═════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def list_integrations(search: str = "") -> dict:
    """
    List available integrations (useful to discover commands for
    execute_integration_command).
    """
    try:
        result = _xsoar().list_integrations(query=search)
    except XSOARError as e:
        return {"error": str(e)}

    configs = result.get("configurations") or []
    instances = result.get("instances") or []
    return {
        "integration_count": len(configs),
        "instance_count": len(instances),
        "integrations": [
            {
                "name": c.get("name"),
                "display": c.get("display"),
                "category": c.get("category"),
                "description": (c.get("description") or "")[:200],
            }
            for c in configs[:50]
        ],
    }


@mcp.tool()
def list_incident_types() -> dict:
    """List all configured incident types."""
    try:
        types = _xsoar().list_incident_types()
    except XSOARError as e:
        return {"error": str(e)}
    return {
        "count": len(types),
        "types": [
            {"id": t.get("id"), "name": t.get("name"),
             "playbook": t.get("playbookId")}
            for t in types
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
#   SERVER / USER TOOLS
# ═════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_server_info() -> dict:
    """Check XSOAR server version and connectivity."""
    try:
        result = _xsoar().server_info()
    except XSOARError as e:
        return {"error": str(e), "connected": False}
    return {
        "connected": True,
        "version": result.get("demistoVersion"),
        "build": result.get("buildNum"),
        "platform": result.get("platform"),
        "read_only_mode": READ_ONLY,
    }


@mcp.tool()
def list_users() -> dict:
    """List XSOAR users. Useful for incident assignment."""
    try:
        users = _xsoar().list_users()
    except XSOARError as e:
        return {"error": str(e)}
    return {
        "count": len(users),
        "users": [
            {"username": u.get("id"), "name": u.get("name"),
             "email": u.get("email", "")}
            for u in users
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
#   MCP RESOURCES
# ═════════════════════════════════════════════════════════════════════════════


@mcp.resource("xsoar://server/info")
def resource_server_info() -> str:
    """Live XSOAR server info and MCP mode."""
    try:
        info = _xsoar().server_info()
        return json.dumps({
            "connected": True,
            "version": info.get("demistoVersion"),
            "build": info.get("buildNum"),
            "platform": info.get("platform"),
            "read_only_mode": READ_ONLY,
        }, indent=2)
    except XSOARError as e:
        return json.dumps({"connected": False, "error": str(e)}, indent=2)


@mcp.resource("xsoar://incidents/recent")
def resource_recent_incidents() -> str:
    """Last 20 incidents (JSON)."""
    try:
        result = _xsoar().search_incidents(query="", size=20)
    except XSOARError as e:
        return json.dumps({"error": str(e)})
    incidents = result.get("data") or []
    return json.dumps({
        "total": result.get("total", len(incidents)),
        "returned": len(incidents),
        "incidents": [fmt_incident(i) for i in incidents],
    }, indent=2)


@mcp.resource("xsoar://incidents/open")
def resource_open_incidents() -> str:
    """Currently open (Active) incidents."""
    try:
        result = _xsoar().search_incidents(query="status:1", size=50)
    except XSOARError as e:
        return json.dumps({"error": str(e)})
    incidents = result.get("data") or []
    return json.dumps({
        "total": result.get("total", len(incidents)),
        "incidents": [fmt_incident(i) for i in incidents],
    }, indent=2)


# ═════════════════════════════════════════════════════════════════════════════
#   MCP PROMPTS
# ═════════════════════════════════════════════════════════════════════════════


@mcp.prompt()
def investigate_incident(incident_id: str) -> str:
    """Run a guided investigation on a specific XSOAR incident."""
    return (
        f"Please investigate XSOAR incident {incident_id} following these steps:\n\n"
        f"1. Use `get_incident('{incident_id}')` to load full details.\n"
        f"2. Use `get_war_room_entries('{incident_id}')` to review the timeline.\n"
        f"3. Use `get_incident_work_plan('{incident_id}')` to check playbook status.\n"
        f"4. Extract any IOCs (IPs, hashes, domains, URLs) from the details and "
        f"for each one call `get_indicator(<value>)` to check reputation.\n"
        f"5. Summarize findings with: severity assessment, suspicious indicators, "
        f"recommended next actions.\n"
        f"6. DO NOT take write actions (close, update, run playbook) without "
        f"asking me for confirmation."
    )


@mcp.prompt()
def triage_phishing() -> str:
    """Triage all recent phishing incidents."""
    return (
        "Please triage recent phishing incidents:\n\n"
        "1. Call `search_incidents(query='type:Phishing AND status:1', size=20)`.\n"
        "2. For each incident, extract email indicators (sender, URLs, attachments) "
        "from the details field.\n"
        "3. For each extracted IOC, call `get_indicator()` to check reputation.\n"
        "4. Rank incidents by calculated severity: number of bad IOCs, sender "
        "reputation, and URL maliciousness.\n"
        "5. Present a prioritized action list with recommendations "
        "(auto-close benign, escalate malicious, request analyst review for "
        "ambiguous cases). Ask me before executing any close/update action."
    )


@mcp.prompt()
def hunt_ioc(ioc_value: str) -> str:
    """Threat-hunt a specific IOC across XSOAR."""
    return (
        f"Hunt the indicator '{ioc_value}' across XSOAR:\n\n"
        f"1. Call `get_indicator('{ioc_value}')` — what is the known reputation?\n"
        f"2. Call `search_incidents(query='{ioc_value}', size=50)` — which "
        f"incidents reference it?\n"
        f"3. For the top 3 incidents, call `get_incident(id)` to retrieve details.\n"
        f"4. Summarize:\n"
        f"   - IOC reputation\n"
        f"   - Incidents affected (count, severity distribution)\n"
        f"   - Timeline: when did we first/last see it?\n"
        f"   - Recommended response (block, monitor, dismiss)"
    )


@mcp.prompt()
def daily_soc_briefing() -> str:
    """Generate a daily SOC briefing."""
    return (
        "Generate today's SOC briefing:\n\n"
        "1. Call `search_incidents(query='created:>=\"now-24h\"', size=100)` for "
        "new incidents in the last 24h.\n"
        "2. Call `search_incidents(query='status:1 AND severity:>=3', size=50)` "
        "for open high/critical incidents.\n"
        "3. For each open critical, call `get_incident_work_plan(id)` to check "
        "playbook progress.\n"
        "4. Present as a briefing with sections:\n"
        "   - 📊 Stats (new, open, closed, by type/severity)\n"
        "   - 🔥 Critical open incidents (need attention)\n"
        "   - ⏸️  Stuck playbooks (tasks waiting)\n"
        "   - 📌 Recommendations"
    )


# ═════════════════════════════════════════════════════════════════════════════
#   Entrypoint
# ═════════════════════════════════════════════════════════════════════════════


def main() -> None:
    logger.info(
        "Starting XSOAR MCP Server (read_only=%s, debug=%s)", READ_ONLY, DEBUG,
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
