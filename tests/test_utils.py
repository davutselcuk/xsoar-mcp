"""Tests for shared utility functions."""

from xsoar_mcp.utils import SCORE_MAP, fmt_indicator


class TestFmtIndicator:
    def test_full(self):
        raw = {
            "id": "IOC-1", "value": "8.8.8.8", "indicator_type": "IP",
            "score": 1, "comment": "Good DNS", "relatedIncCount": 5,
        }
        r = fmt_indicator(raw)
        assert r["id"] == "IOC-1"
        assert r["value"] == "8.8.8.8"
        assert r["score"] == "Good"
        assert r["score_code"] == 1
        assert r["related_incidents"] == 5

    def test_empty(self):
        r = fmt_indicator({})
        assert r["id"] is None
        assert r["score"] == "Unknown"

    def test_all_scores(self):
        for code, label in SCORE_MAP.items():
            assert fmt_indicator({"score": code})["score"] == label
