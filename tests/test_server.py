"""Tests for MCP server formatting and tool logic."""

import pytest
from unittest.mock import patch, MagicMock
from xsoar_mcp.server import _fmt_incident, _SEVERITY, _STATUS


class TestFmtIncident:
    def test_full_incident(self):
        raw = {
            "id": "INC-001",
            "name": "Phishing attempt",
            "type": "Phishing",
            "severity": 3,
            "status": 1,
            "owner": "analyst1",
            "occurred": "2024-01-01T10:00:00Z",
            "created": "2024-01-01T10:00:00Z",
            "modified": "2024-01-01T11:00:00Z",
            "closed": None,
            "closeReason": None,
            "details": "Suspicious email received",
            "labels": [{"type": "Category", "value": "Email"}],
            "playbookId": "PB-001",
        }
        result = _fmt_incident(raw)

        assert result["id"] == "INC-001"
        assert result["name"] == "Phishing attempt"
        assert result["severity"] == "High"
        assert result["severity_code"] == 3
        assert result["status"] == "Active"
        assert result["owner"] == "analyst1"
        assert result["playbook"] == "PB-001"

    def test_empty_incident(self):
        result = _fmt_incident({})
        assert result["id"] is None
        assert result["name"] is None
        assert result["severity"] == "Unknown"
        assert result["status"] == "Pending"
        assert result["details"] == ""
        assert result["labels"] == []

    def test_all_severity_levels(self):
        for code, label in _SEVERITY.items():
            result = _fmt_incident({"severity": code})
            assert result["severity"] == label

    def test_all_status_values(self):
        for code, label in _STATUS.items():
            result = _fmt_incident({"status": code})
            assert result["status"] == label

    def test_details_truncated_at_300(self):
        long_details = "x" * 500
        result = _fmt_incident({"details": long_details})
        assert len(result["details"]) == 300

    def test_unknown_severity_returns_string(self):
        result = _fmt_incident({"severity": 99})
        assert result["severity"] == "99"

    def test_unknown_status_returns_string(self):
        result = _fmt_incident({"status": 99})
        assert result["status"] == "99"


class TestMcpTools:
    """Test MCP tools with mocked HTTP calls."""

    def _make_mock_req(self, return_value):
        return patch("xsoar_mcp.server._req", return_value=return_value)

    def test_get_server_info(self):
        from xsoar_mcp.server import get_server_info
        mock_resp = {"demistoVersion": "6.10.0", "buildNum": "12345", "platform": "linux"}
        with self._make_mock_req(mock_resp):
            result = get_server_info()
        assert result["connected"] is True
        assert result["version"] == "6.10.0"
        assert result["build"] == "12345"

    def test_search_incidents_empty(self):
        from xsoar_mcp.server import search_incidents
        with self._make_mock_req({"data": [], "total": 0}):
            result = search_incidents()
        assert result["total"] == 0
        assert result["returned"] == 0
        assert result["incidents"] == []

    def test_search_incidents_with_results(self):
        from xsoar_mcp.server import search_incidents
        raw = [{"id": "1", "name": "Test", "severity": 2, "status": 1}]
        with self._make_mock_req({"data": raw, "total": 1}):
            result = search_incidents(query="type:Phishing", size=10)
        assert result["total"] == 1
        assert result["returned"] == 1
        assert result["incidents"][0]["severity"] == "Medium"

    def test_create_incident(self):
        from xsoar_mcp.server import create_incident
        with self._make_mock_req({"id": "INC-100", "name": "Test Incident"}):
            result = create_incident(name="Test Incident", severity=3)
        assert result["created"] is True
        assert result["id"] == "INC-100"

    def test_close_incident(self):
        from xsoar_mcp.server import close_incident
        with self._make_mock_req({"status": "ok"}):
            result = close_incident("INC-001", close_reason="Resolved")
        assert result["closed"] is True
        assert result["id"] == "INC-001"

    def test_search_indicators_empty(self):
        from xsoar_mcp.server import search_indicators
        with self._make_mock_req({"iocObjects": [], "total": 0}):
            result = search_indicators(query="8.8.8.8")
        assert result["total"] == 0
        assert result["indicators"] == []

    def test_get_indicator_found(self):
        from xsoar_mcp.server import get_indicator
        raw_ioc = {"id": "IOC-1", "value": "8.8.8.8", "indicator_type": "IP", "score": 1}
        with self._make_mock_req({"iocObjects": [raw_ioc]}):
            result = get_indicator("8.8.8.8")
        assert result["found"] is True
        assert result["value"] == "8.8.8.8"

    def test_get_indicator_not_found(self):
        from xsoar_mcp.server import get_indicator
        with self._make_mock_req({"iocObjects": []}):
            result = get_indicator("unknown")
        assert result["found"] is False

    def test_list_users(self):
        from xsoar_mcp.server import list_users
        users = [{"id": "user1", "name": "Alice", "email": "alice@example.com"}]
        with self._make_mock_req(users):
            result = list_users()
        assert result["count"] == 1
        assert result["users"][0]["username"] == "user1"

    def test_add_war_room_entry(self):
        from xsoar_mcp.server import add_war_room_entry
        with self._make_mock_req({"status": "ok"}):
            result = add_war_room_entry("INC-001", "Investigation started")
        assert result["entry_added"] is True

    def test_get_war_room_entries(self):
        from xsoar_mcp.server import get_war_room_entries
        entries = [{"id": "E1", "type": 1, "created": "2024-01-01", "user": "alice", "contents": "Note"}]
        with self._make_mock_req({"entries": entries}):
            result = get_war_room_entries("INC-001")
        assert result["entry_count"] == 1
        assert result["entries"][0]["user"] == "alice"
