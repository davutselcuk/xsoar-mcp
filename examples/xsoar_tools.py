"""
XSOAR tool definitions in OpenAI function-calling format, plus execution logic.
Used by the Python CLI agent (agent.py).
"""

import json
from xsoar_mcp.client import XSOARClient
from xsoar_mcp.utils import fmt_incident

# ── Tool Definitions (OpenAI tools format) ────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_incidents",
            "description": "Search XSOAR incidents. Filter by date, type, severity, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Lucene query. Example: 'type:Phishing AND severity:3'. Empty returns all.",
                    },
                    "size": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 20)",
                        "default": 20,
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number, starting from 0",
                        "default": 0,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_incident",
            "description": "Get all details for a specific incident ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_id": {"type": "string", "description": "XSOAR incident ID"},
                },
                "required": ["incident_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_incident",
            "description": "Create a new XSOAR incident.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Incident name (required)"},
                    "type": {"type": "string", "description": "Incident type: Phishing, Malware, Unclassified, etc."},
                    "severity": {
                        "type": "integer",
                        "description": "Severity: 0=Unknown, 1=Low, 2=Medium, 3=High, 4=Critical",
                    },
                    "details": {"type": "string", "description": "Description"},
                    "owner": {"type": "string", "description": "Assigned username"},
                    "playbook_id": {"type": "string", "description": "Playbook ID to auto-start"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_incident",
            "description": "Update an existing incident (severity, owner, status, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_id": {"type": "string", "description": "Incident ID to update"},
                    "severity": {"type": "integer", "description": "New severity (0-4)"},
                    "owner": {"type": "string", "description": "New assigned user"},
                    "status": {
                        "type": "integer",
                        "description": "Status: 0=Pending, 1=Active, 2=Closed, 3=Archived",
                    },
                    "details": {"type": "string", "description": "New description"},
                },
                "required": ["incident_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_incident",
            "description": "Close an incident.",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_id": {"type": "string", "description": "Incident ID to close"},
                    "close_reason": {
                        "type": "string",
                        "description": "Close reason: Resolved, False Positive, Duplicate, etc.",
                    },
                    "close_notes": {"type": "string", "description": "Closing notes"},
                },
                "required": ["incident_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_war_room_entry",
            "description": "Add a note or comment to an incident's War Room.",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_id": {"type": "string", "description": "Target incident ID"},
                    "content": {"type": "string", "description": "Content to add (supports Markdown)"},
                },
                "required": ["incident_id", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_war_room_entries",
            "description": "Get War Room entries for an incident.",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_id": {"type": "string", "description": "Incident ID"},
                    "max_entries": {"type": "integer", "description": "Max entries to return", "default": 50},
                },
                "required": ["incident_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_indicators",
            "description": "Search threat indicators (IOCs): IPs, domains, file hashes, URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search value, e.g. '8.8.8.8'"},
                    "ioc_type": {
                        "type": "string",
                        "description": "Type filter: IP, Domain, File, URL, CVE, etc.",
                    },
                    "size": {"type": "integer", "description": "Max results", "default": 20},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_playbooks",
            "description": "List available XSOAR playbooks.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_playbook_on_incident",
            "description": "Run a specific playbook on an incident.",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_id": {"type": "string", "description": "Target incident ID"},
                    "playbook_id": {"type": "string", "description": "Playbook ID to run"},
                },
                "required": ["incident_id", "playbook_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_server_info",
            "description": "Test connectivity to XSOAR and return version info.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ── Tool Execution ────────────────────────────────────────────────────────────

def execute_tool(tool_name: str, args: dict, client: XSOARClient) -> str:
    """Execute a tool called by the AI; returns result as JSON string."""
    try:
        result = _dispatch(tool_name, args, client)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def _dispatch(name: str, args: dict, client: XSOARClient) -> dict:
    if name == "get_server_info":
        r = client.server_info()
        return {"connected": True, "version": r.get("demistoVersion"),
                "build": r.get("buildNum")}

    elif name == "search_incidents":
        r = client.search_incidents(
            query=args.get("query", ""),
            size=args.get("size", 20),
            page=args.get("page", 0),
        )
        incidents = r.get("data") or []
        return {
            "total": r.get("total", len(incidents)),
            "returned": len(incidents),
            "incidents": [fmt_incident(i) for i in incidents],
        }

    elif name == "get_incident":
        return fmt_incident(client.get_incident(args["incident_id"]))

    elif name == "create_incident":
        r = client.create_incident(
            name=args["name"],
            type=args.get("type", "Unclassified"),
            severity=args.get("severity", 1),
            details=args.get("details", ""),
            owner=args.get("owner", ""),
            playbook_id=args.get("playbook_id", ""),
        )
        return {"created": True, "id": r.get("id"), "name": r.get("name")}

    elif name == "update_incident":
        fields = {k: v for k, v in args.items() if k != "incident_id"}
        client.update_incident(args["incident_id"], **fields)
        return {"updated": True, "id": args["incident_id"]}

    elif name == "close_incident":
        client.close_incident(
            args["incident_id"],
            close_reason=args.get("close_reason", "Resolved"),
            close_notes=args.get("close_notes", ""),
        )
        return {"closed": True, "id": args["incident_id"]}

    elif name == "add_war_room_entry":
        client.add_entry(args["incident_id"], args["content"])
        return {"added": True}

    elif name == "get_war_room_entries":
        r = client.get_entries(args["incident_id"], args.get("max_entries", 50))
        entries = r.get("entries") or []
        return {
            "count": len(entries),
            "entries": [
                {"id": e.get("id"), "user": e.get("user"),
                 "created": e.get("created"),
                 "content": (e.get("contents") or "")[:300]}
                for e in entries
            ],
        }

    elif name == "search_indicators":
        r = client.search_indicators(
            query=args.get("query", ""),
            ioc_type=args.get("ioc_type", ""),
            size=args.get("size", 20),
        )
        items = r.get("iocObjects") or []
        return {
            "total": r.get("total", len(items)),
            "indicators": [
                {"id": i.get("id"), "value": i.get("value"),
                 "type": i.get("indicator_type"), "score": i.get("score")}
                for i in items
            ],
        }

    elif name == "list_playbooks":
        playbooks = client.list_playbooks()
        return {
            "count": len(playbooks),
            "playbooks": [
                {"id": p.get("id"), "name": p.get("name"),
                 "description": p.get("description", "")}
                for p in playbooks
            ],
        }

    elif name == "run_playbook_on_incident":
        client.run_playbook(args["incident_id"], args["playbook_id"])
        return {"started": True, "incident_id": args["incident_id"],
                "playbook_id": args["playbook_id"]}

    else:
        return {"error": f"Unknown tool: {name}"}
