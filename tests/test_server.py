"""Tests for MCP server tools, resources, prompts, and read-only mode."""

import importlib
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from xsoar_mcp.utils import SEVERITY_MAP, STATUS_MAP, fmt_incident

FAKE_ENV = {
    "XSOAR_URL": "https://xsoar.test",
    "XSOAR_API_KEY": "test-key-123",
    "XSOAR_VERIFY_SSL": "true",
}


# ── fmt_incident ──────────────────────────────────────────────────────────────

class TestFmtIncident:
    def test_full_incident(self):
        raw = {
            "id": "INC-001", "name": "Phishing attempt", "type": "Phishing",
            "severity": 3, "status": 1, "owner": "analyst1",
            "occurred": "2024-01-01T10:00:00Z", "created": "2024-01-01T10:00:00Z",
            "playbookId": "PB-001",
        }
        r = fmt_incident(raw)
        assert r["id"] == "INC-001"
        assert r["severity"] == "High"
        assert r["severity_code"] == 3
        assert r["status"] == "Active"
        assert r["playbook"] == "PB-001"

    def test_empty_incident(self):
        r = fmt_incident({})
        assert r["id"] is None
        assert r["severity"] == "Unknown"
        assert r["status"] == "Pending"
        assert r["labels"] == []

    def test_all_severity_levels(self):
        for code, label in SEVERITY_MAP.items():
            assert fmt_incident({"severity": code})["severity"] == label

    def test_all_status_values(self):
        for code, label in STATUS_MAP.items():
            assert fmt_incident({"status": code})["status"] == label

    def test_details_truncated_at_300(self):
        r = fmt_incident({"details": "x" * 500})
        assert len(r["details"]) == 300

    def test_unknown_severity_returns_string(self):
        assert fmt_incident({"severity": 99})["severity"] == "99"


# ── MCP tools (mock the XSOARClient) ─────────────────────────────────────────

@pytest.fixture
def server_module():
    """Import server freshly with fake env (to reset READ_ONLY between tests)."""
    with patch.dict(os.environ, FAKE_ENV, clear=False):
        if "xsoar_mcp.server" in importlib.sys.modules:
            del importlib.sys.modules["xsoar_mcp.server"]
        import xsoar_mcp.server as srv
        importlib.reload(srv)
        yield srv
    if "xsoar_mcp.server" in importlib.sys.modules:
        del importlib.sys.modules["xsoar_mcp.server"]


def _mock_client(server_module, **method_returns):
    """Replace server_module._xsoar() to return a mock with given method returns."""
    mock = MagicMock()
    for name, value in method_returns.items():
        getattr(mock, name).return_value = value
    server_module._client = mock
    return mock


class TestMcpTools:
    def test_get_server_info(self, server_module):
        _mock_client(server_module, server_info={
            "demistoVersion": "6.10.0", "buildNum": "12345", "platform": "linux",
        })
        r = server_module.get_server_info()
        assert r["connected"] is True
        assert r["version"] == "6.10.0"

    def test_search_incidents_empty(self, server_module):
        _mock_client(server_module, search_incidents={"data": [], "total": 0})
        r = server_module.search_incidents()
        assert r["total"] == 0
        assert r["incidents"] == []

    def test_search_incidents_with_results(self, server_module):
        raw = [{"id": "1", "name": "Test", "severity": 2, "status": 1}]
        _mock_client(server_module, search_incidents={"data": raw, "total": 1})
        r = server_module.search_incidents(query="type:Phishing", size=10)
        assert r["total"] == 1
        assert r["incidents"][0]["severity"] == "Medium"

    def test_create_incident(self, server_module):
        _mock_client(server_module, create_incident={"id": "INC-100", "name": "Test"})
        r = server_module.create_incident(name="Test", severity=3)
        assert r["created"] is True
        assert r["id"] == "INC-100"

    def test_close_incident(self, server_module):
        _mock_client(server_module, close_incident={"status": "ok"})
        r = server_module.close_incident("INC-001", close_reason="Resolved")
        assert r["closed"] is True

    def test_reopen_incident(self, server_module):
        _mock_client(server_module, reopen_incident={"status": "ok"})
        r = server_module.reopen_incident("INC-001")
        assert r["reopened"] is True

    def test_search_indicators_empty(self, server_module):
        _mock_client(server_module, search_indicators={"iocObjects": [], "total": 0})
        r = server_module.search_indicators(query="8.8.8.8")
        assert r["total"] == 0

    def test_get_indicator_found(self, server_module):
        ioc = {"id": "IOC-1", "value": "8.8.8.8", "indicator_type": "IP", "score": 1}
        _mock_client(server_module, search_indicators={"iocObjects": [ioc]})
        r = server_module.get_indicator("8.8.8.8")
        assert r["found"] is True
        assert r["value"] == "8.8.8.8"
        assert r["score"] == "Good"

    def test_get_indicator_not_found(self, server_module):
        _mock_client(server_module, search_indicators={"iocObjects": []})
        r = server_module.get_indicator("unknown")
        assert r["found"] is False

    def test_create_indicator(self, server_module):
        _mock_client(server_module, create_indicator={"id": "IOC-1"})
        r = server_module.create_indicator(value="1.2.3.4", indicator_type="IP", score=3)
        assert r["created"] is True
        assert r["score"] == "Bad"

    def test_list_users(self, server_module):
        users = [{"id": "u1", "name": "Alice", "email": "a@x.com"}]
        _mock_client(server_module, list_users=users)
        r = server_module.list_users()
        assert r["count"] == 1
        assert r["users"][0]["username"] == "u1"

    def test_list_integrations(self, server_module):
        configs = [{"name": "VT", "display": "VirusTotal", "category": "Threat Intel"}]
        _mock_client(server_module, list_integrations={"configurations": configs, "instances": []})
        r = server_module.list_integrations()
        assert r["integration_count"] == 1
        assert r["integrations"][0]["display"] == "VirusTotal"

    def test_execute_integration_command(self, server_module):
        entries = [{"id": "E1", "type": 1, "contents": "query result"}]
        _mock_client(server_module, execute_command=entries)
        r = server_module.execute_integration_command("INC-001", "!ip ip=8.8.8.8")
        assert r["executed"] is True
        assert r["entry_count"] == 1

    def test_add_war_room_entry(self, server_module):
        _mock_client(server_module, add_entry={"status": "ok"})
        r = server_module.add_war_room_entry("INC-001", "note")
        assert r["entry_added"] is True


# ── Read-only mode ────────────────────────────────────────────────────────────

class TestReadOnlyMode:
    @pytest.fixture
    def readonly_server(self):
        env = {**FAKE_ENV, "XSOAR_READ_ONLY": "true"}
        with patch.dict(os.environ, env, clear=False):
            if "xsoar_mcp.server" in importlib.sys.modules:
                del importlib.sys.modules["xsoar_mcp.server"]
            import xsoar_mcp.server as srv
            importlib.reload(srv)
            yield srv
        if "xsoar_mcp.server" in importlib.sys.modules:
            del importlib.sys.modules["xsoar_mcp.server"]

    def test_read_only_flag_set(self, readonly_server):
        assert readonly_server.READ_ONLY is True

    def test_create_incident_blocked(self, readonly_server):
        _mock_client(readonly_server, create_incident={"id": "X"})
        r = readonly_server.create_incident(name="X")
        assert r["error"] == "read_only_mode"
        assert "XSOAR_READ_ONLY" in r["message"]

    def test_close_incident_blocked(self, readonly_server):
        r = readonly_server.close_incident("INC-1")
        assert r["error"] == "read_only_mode"

    def test_execute_command_blocked(self, readonly_server):
        r = readonly_server.execute_integration_command("INC-1", "!ip ip=1.1.1.1")
        assert r["error"] == "read_only_mode"

    def test_read_tool_still_works(self, readonly_server):
        _mock_client(readonly_server, search_incidents={"data": [], "total": 0})
        r = readonly_server.search_incidents()
        assert "error" not in r
        assert r["total"] == 0


# ── Resources ─────────────────────────────────────────────────────────────────

class TestResources:
    def test_server_info_resource(self, server_module):
        _mock_client(server_module, server_info={
            "demistoVersion": "6.10.0", "buildNum": "12345", "platform": "linux",
        })
        result = server_module.resource_server_info()
        parsed = json.loads(result)
        assert parsed["connected"] is True
        assert parsed["version"] == "6.10.0"

    def test_recent_incidents_resource(self, server_module):
        _mock_client(server_module, search_incidents={
            "data": [{"id": "1", "name": "Test", "severity": 2, "status": 1}],
            "total": 1,
        })
        result = server_module.resource_recent_incidents()
        parsed = json.loads(result)
        assert parsed["total"] == 1


# ── Prompts ───────────────────────────────────────────────────────────────────

class TestPrompts:
    def test_investigate_incident_prompt(self, server_module):
        p = server_module.investigate_incident("INC-123")
        assert "INC-123" in p
        assert "get_incident" in p

    def test_triage_phishing_prompt(self, server_module):
        p = server_module.triage_phishing()
        assert "Phishing" in p
        assert "search_incidents" in p

    def test_hunt_ioc_prompt(self, server_module):
        p = server_module.hunt_ioc("8.8.8.8")
        assert "8.8.8.8" in p

    def test_daily_briefing_prompt(self, server_module):
        p = server_module.daily_soc_briefing()
        assert "SOC" in p
