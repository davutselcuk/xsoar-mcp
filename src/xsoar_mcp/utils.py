"""Shared constants and formatting helpers."""

from typing import Any

SEVERITY_MAP: dict[int, str] = {
    0: "Unknown",
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Critical",
}

STATUS_MAP: dict[int, str] = {
    0: "Pending",
    1: "Active",
    2: "Closed",
    3: "Archived",
}

# Indicator score (reputation)
SCORE_MAP: dict[int, str] = {
    0: "Unknown",
    1: "Good",
    2: "Suspicious",
    3: "Bad",
}


def fmt_incident(i: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw XSOAR incident dict to a readable format."""
    return {
        "id": i.get("id"),
        "name": i.get("name"),
        "type": i.get("type"),
        "severity": SEVERITY_MAP.get(i.get("severity", 0), str(i.get("severity"))),
        "severity_code": i.get("severity"),
        "status": STATUS_MAP.get(i.get("status", 0), str(i.get("status"))),
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


def fmt_indicator(ind: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw XSOAR indicator dict to a readable format."""
    score_code = ind.get("score", 0)
    return {
        "id": ind.get("id"),
        "value": ind.get("value"),
        "type": ind.get("indicator_type"),
        "score": SCORE_MAP.get(score_code, str(score_code)),
        "score_code": score_code,
        "expiration": ind.get("expiration"),
        "comment": ind.get("comment", ""),
        "timestamp": ind.get("timestamp"),
        "modified": ind.get("modified"),
        "related_incidents": ind.get("relatedIncCount", 0),
    }
