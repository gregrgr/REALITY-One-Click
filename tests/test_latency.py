from __future__ import annotations

import unittest
from unittest.mock import patch

from panel.latency import parse_cache_seconds, parse_timeout, probe_exit_latency, probe_exit_latency_cached


class LatencyProbeTest(unittest.TestCase):
    def test_latency_uses_direct_route(self) -> None:
        with patch(
            "panel.latency.request_url",
            side_effect=[
                {"latency_ms": 45, "status_code": 204, "body": ""},
                {"latency_ms": 30, "status_code": 200, "body": "203.0.113.10"},
            ],
        ):
            result = probe_exit_latency({})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["route"], "direct")
        self.assertEqual(result["exit_http_ms"], 45)
        self.assertEqual(result["exit_ip"], "203.0.113.10")

    def test_timeout_is_clamped(self) -> None:
        self.assertEqual(parse_timeout({"latency_timeout_seconds": "0.1"}), 1.0)
        self.assertEqual(parse_timeout({"latency_timeout_seconds": "60"}), 30.0)
        self.assertEqual(parse_timeout({"latency_timeout_seconds": "bad"}), 5.0)

    def test_cache_seconds_is_clamped(self) -> None:
        self.assertEqual(parse_cache_seconds({"latency_cache_seconds": "-1"}), 0.0)
        self.assertEqual(parse_cache_seconds({"latency_cache_seconds": "999"}), 300.0)
        self.assertEqual(parse_cache_seconds({"latency_cache_seconds": "bad"}), 30.0)

    def test_cached_latency_reuses_probe_result(self) -> None:
        settings = {"latency_cache_seconds": "30"}

        with patch(
            "panel.latency.request_url",
            side_effect=[
                {"latency_ms": 45, "status_code": 204, "body": ""},
                {"latency_ms": 30, "status_code": 200, "body": "203.0.113.10"},
            ],
        ) as request:
            first = probe_exit_latency_cached(settings)
            second = probe_exit_latency_cached(settings)

        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(second["exit_ip"], "203.0.113.10")
        self.assertEqual(request.call_count, 2)


if __name__ == "__main__":
    unittest.main()
