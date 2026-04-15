"""Tests for XSOARClient."""

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from xsoar_mcp.client import XSOARClient, XSOARError

FAKE_ENV = {
    "XSOAR_URL": "https://xsoar.test",
    "XSOAR_API_KEY": "test-key-123",
    "XSOAR_VERIFY_SSL": "true",
}


def _fresh_client():
    """Build an XSOARClient with FAKE_ENV without making real HTTP calls."""
    with patch.dict(os.environ, FAKE_ENV, clear=True):
        return XSOARClient()


class TestInit:
    def test_missing_url_raises(self):
        with patch.dict(os.environ, {"XSOAR_API_KEY": "key"}, clear=True):
            with pytest.raises(ValueError, match="XSOAR_URL"):
                XSOARClient()

    def test_missing_api_key_raises(self):
        with patch.dict(os.environ, {"XSOAR_URL": "https://xsoar.test"}, clear=True):
            with pytest.raises(ValueError):
                XSOARClient()

    def test_successful_init(self):
        c = _fresh_client()
        assert c.base_url == "https://xsoar.test"
        assert c.api_key == "test-key-123"
        assert c.verify_ssl is True
        c.close()

    def test_trailing_slash_stripped(self):
        env = {**FAKE_ENV, "XSOAR_URL": "https://xsoar.test/"}
        with patch.dict(os.environ, env, clear=True):
            c = XSOARClient()
        assert not c.base_url.endswith("/")
        c.close()

    def test_verify_ssl_false(self):
        env = {**FAKE_ENV, "XSOAR_VERIFY_SSL": "false"}
        with patch.dict(os.environ, env, clear=True):
            c = XSOARClient()
        assert c.verify_ssl is False
        c.close()

    def test_constructor_args_override_env(self):
        c = XSOARClient(base_url="https://override.test", api_key="abc",
                        verify_ssl=False)
        assert c.base_url == "https://override.test"
        assert c.api_key == "abc"
        assert c.verify_ssl is False
        c.close()

    def test_context_manager(self):
        with _fresh_client() as c:
            assert c.base_url == "https://xsoar.test"


class TestHeaders:
    def test_headers(self):
        c = _fresh_client()
        h = c._headers()
        assert h["Authorization"] == "test-key-123"
        assert h["x-xdr-auth-id"] == "1"
        assert h["Content-Type"] == "application/json"
        c.close()


class TestRequest:
    def _mk_response(self, status=200, json_data=None):
        r = MagicMock()
        r.status_code = status
        r.content = b'{}' if json_data is not None else b''
        r.json.return_value = json_data or {}
        r.raise_for_status = MagicMock()
        r.text = ""
        return r

    def test_request_success(self):
        c = _fresh_client()
        with patch.object(c._client, "request", return_value=self._mk_response(json_data={"ok": 1})):
            assert c.request("GET", "/x") == {"ok": 1}
        c.close()

    def test_request_4xx_raises_xsoar_error(self):
        c = _fresh_client()
        err_resp = MagicMock()
        err_resp.status_code = 401
        err_resp.text = "Unauthorized"
        err = httpx.HTTPStatusError("boom", request=MagicMock(), response=err_resp)

        resp = self._mk_response(status=401)
        resp.raise_for_status.side_effect = err

        with patch.object(c._client, "request", return_value=resp):
            with pytest.raises(XSOARError, match="401"):
                c.request("GET", "/x")
        c.close()

    def test_request_retries_on_5xx(self):
        c = _fresh_client()
        bad = self._mk_response(status=503)
        bad.raise_for_status.side_effect = httpx.HTTPStatusError(
            "boom", request=MagicMock(), response=MagicMock(status_code=503, text="")
        )
        good = self._mk_response(json_data={"ok": 1})
        with patch.object(c._client, "request", side_effect=[bad, bad, good]) as mock_req:
            with patch("time.sleep"):  # don't actually sleep
                result = c.request("GET", "/x")
        assert result == {"ok": 1}
        assert mock_req.call_count == 3
        c.close()


class TestApiMethods:
    def test_search_incidents_body(self):
        c = _fresh_client()
        with patch.object(c, "request", return_value={"data": []}) as mock:
            c.search_incidents(query="type:Phishing", size=5, page=1)
        body = mock.call_args.kwargs["json"]
        assert body["filter"]["query"] == "type:Phishing"
        assert body["filter"]["size"] == 5
        c.close()

    def test_close_incident_sends_status_2(self):
        c = _fresh_client()
        with patch.object(c, "request", return_value={}) as mock:
            c.close_incident("INC-1", close_reason="Resolved")
        body = mock.call_args.kwargs["json"]
        assert body["status"] == 2
        assert body["closeReason"] == "Resolved"
        c.close()

    def test_reopen_incident(self):
        c = _fresh_client()
        with patch.object(c, "request", return_value={}) as mock:
            c.reopen_incident("INC-1")
        assert mock.call_args.args == ("POST", "/xsoar/incident/reopen")
        c.close()

    def test_execute_command_adds_bang(self):
        c = _fresh_client()
        with patch.object(c, "request", return_value=[]) as mock:
            c.execute_command("INC-1", "ip ip=8.8.8.8")  # no leading !
        body = mock.call_args.kwargs["json"]
        assert body["data"].startswith("!")
        assert body["investigationId"] == "INC-1"
        c.close()

    def test_search_indicators_with_type(self):
        c = _fresh_client()
        with patch.object(c, "request", return_value={}) as mock:
            c.search_indicators(query="8.8.8.8", ioc_type="IP")
        body = mock.call_args.kwargs["json"]
        assert body["type"] == "IP"
        c.close()

    def test_create_indicator_body(self):
        c = _fresh_client()
        with patch.object(c, "request", return_value={}) as mock:
            c.create_indicator(value="1.2.3.4", indicator_type="IP", score=3,
                               comment="bad IP", source="test")
        body = mock.call_args.kwargs["json"]
        assert body["indicator"]["value"] == "1.2.3.4"
        assert body["indicator"]["score"] == 3
        c.close()
