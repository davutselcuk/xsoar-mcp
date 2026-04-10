"""Tests for XSOARClient initialization and request handling."""

import os
import pytest
from unittest.mock import patch, MagicMock
from xsoar_mcp.client import XSOARClient


FAKE_ENV = {
    "XSOAR_URL": "https://xsoar.test",
    "XSOAR_API_KEY": "test-key-123",
    "XSOAR_VERIFY_SSL": "true",
}


class TestXSOARClientInit:
    def test_missing_url_raises(self):
        with patch.dict(os.environ, {"XSOAR_API_KEY": "key"}, clear=True):
            with pytest.raises(ValueError, match="XSOAR_URL"):
                XSOARClient()

    def test_missing_api_key_raises(self):
        with patch.dict(os.environ, {"XSOAR_URL": "https://xsoar.test"}, clear=True):
            with pytest.raises(ValueError, match="XSOAR_API_KEY"):
                XSOARClient()

    def test_both_missing_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                XSOARClient()

    def test_successful_init(self):
        with patch.dict(os.environ, FAKE_ENV):
            client = XSOARClient()
        assert client.base_url == "https://xsoar.test"
        assert client.api_key == "test-key-123"
        assert client.verify_ssl is True

    def test_trailing_slash_stripped(self):
        env = {**FAKE_ENV, "XSOAR_URL": "https://xsoar.test/"}
        with patch.dict(os.environ, env):
            client = XSOARClient()
        assert not client.base_url.endswith("/")

    def test_verify_ssl_false(self):
        env = {**FAKE_ENV, "XSOAR_VERIFY_SSL": "false"}
        with patch.dict(os.environ, env):
            client = XSOARClient()
        assert client.verify_ssl is False

    def test_verify_ssl_default_true(self):
        env = {k: v for k, v in FAKE_ENV.items() if k != "XSOAR_VERIFY_SSL"}
        with patch.dict(os.environ, env, clear=True):
            client = XSOARClient()
        assert client.verify_ssl is True


class TestXSOARClientHeaders:
    def _get_client(self):
        with patch.dict(os.environ, FAKE_ENV):
            return XSOARClient()

    def test_headers_contain_auth(self):
        client = self._get_client()
        headers = client._headers()
        assert headers["Authorization"] == "test-key-123"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"


class TestXSOARClientRequests:
    def _get_client(self):
        with patch.dict(os.environ, FAKE_ENV):
            return XSOARClient()

    def _mock_response(self, json_data=None, status_code=200):
        mock = MagicMock()
        mock.status_code = status_code
        mock.content = b'{}' if json_data is not None else b''
        mock.json.return_value = json_data or {}
        mock.raise_for_status = MagicMock()
        return mock

    def test_search_incidents_builds_correct_body(self):
        client = self._get_client()
        with patch.object(client, "request", return_value={"data": [], "total": 0}) as mock_req:
            client.search_incidents(query="type:Phishing", size=5, page=1)
        mock_req.assert_called_once()
        call_kwargs = mock_req.call_args
        body = call_kwargs[1]["json"]
        assert body["filter"]["query"] == "type:Phishing"
        assert body["filter"]["size"] == 5
        assert body["filter"]["page"] == 1

    def test_get_incident_uses_correct_path(self):
        client = self._get_client()
        with patch.object(client, "request", return_value={}) as mock_req:
            client.get_incident("INC-999")
        mock_req.assert_called_once_with("GET", "/xsoar/incident/INC-999")

    def test_close_incident_sends_status_2(self):
        client = self._get_client()
        with patch.object(client, "request", return_value={}) as mock_req:
            client.close_incident("INC-001", close_reason="Resolved", close_notes="Done")
        body = mock_req.call_args[1]["json"]
        assert body["status"] == 2
        assert body["closeReason"] == "Resolved"

    def test_search_indicators_with_type_filter(self):
        client = self._get_client()
        with patch.object(client, "request", return_value={}) as mock_req:
            client.search_indicators(query="8.8.8.8", ioc_type="IP", size=10)
        body = mock_req.call_args[1]["json"]
        assert body["type"] == "IP"
        assert body["query"] == "8.8.8.8"

    def test_search_indicators_no_type_filter(self):
        client = self._get_client()
        with patch.dict(os.environ, FAKE_ENV):
            with patch.object(client, "request", return_value={}) as mock_req:
                client.search_indicators(query="malware.com")
        body = mock_req.call_args[1]["json"]
        assert "type" not in body
