from __future__ import annotations

import unittest
from unittest.mock import patch

from panel.latency import parse_cache_seconds, parse_timeout, probe_exit_latency, probe_exit_latency_cached


class LatencyProbeTest(unittest.TestCase):
    def test_relay_latency_uses_egress_socks_backend(self) -> None:
        settings = {
            "node_role": "relay",
            "egress_tailscale_ip": "100.64.10.20",
            "egress_backend_port": "10808",
            "egress_backend_protocol": "socks",
            "latency_probe_url": "https://example.com/generate_204",
            "latency_ip_check_url": "https://api.example.com/ip",
            "latency_timeout_seconds": "3",
        }

        with (
            patch("panel.latency.measure_tcp_connect", return_value=9) as tcp_check,
            patch(
                "panel.latency.request_url",
                side_effect=[
                    {"latency_ms": 123, "status_code": 204, "body": ""},
                    {"latency_ms": 80, "status_code": 200, "body": "198.51.100.9\n"},
                ],
            ) as request,
        ):
            result = probe_exit_latency(settings)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["route"], "relay-egress-socks")
        self.assertEqual(result["backend"], "100.64.10.20:10808")
        self.assertEqual(result["backend_tcp_ms"], 9)
        self.assertEqual(result["exit_http_ms"], 123)
        self.assertEqual(result["exit_ip"], "198.51.100.9")
        tcp_check.assert_called_once_with("100.64.10.20", 10808, 3.0)
        self.assertEqual(request.call_args_list[0].kwargs["socks_proxy"], ("100.64.10.20", 10808))
        self.assertEqual(request.call_args_list[1].kwargs["socks_proxy"], ("100.64.10.20", 10808))

    def test_single_latency_uses_direct_route(self) -> None:
        settings = {"node_role": "single"}

        with (
            patch("panel.latency.measure_tcp_connect") as tcp_check,
            patch(
                "panel.latency.request_url",
                side_effect=[
                    {"latency_ms": 45, "status_code": 204, "body": ""},
                    {"latency_ms": 30, "status_code": 200, "body": "203.0.113.10"},
                ],
            ) as request,
        ):
            result = probe_exit_latency(settings)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["route"], "direct")
        self.assertEqual(result["exit_http_ms"], 45)
        self.assertEqual(result["exit_ip"], "203.0.113.10")
        tcp_check.assert_not_called()
        self.assertIsNone(request.call_args_list[0].kwargs["socks_proxy"])
        self.assertIsNone(request.call_args_list[1].kwargs["socks_proxy"])

    def test_relay_latency_fails_without_egress_ip(self) -> None:
        result = probe_exit_latency({"node_role": "relay"})

        self.assertEqual(result["status"], "failed")
        self.assertIn("egress_tailscale_ip", result["error"])
        self.assertIsNone(result["exit_http_ms"])

    def test_timeout_is_clamped(self) -> None:
        self.assertEqual(parse_timeout({"latency_timeout_seconds": "0.1"}), 1.0)
        self.assertEqual(parse_timeout({"latency_timeout_seconds": "60"}), 30.0)
        self.assertEqual(parse_timeout({"latency_timeout_seconds": "bad"}), 5.0)

    def test_cache_seconds_is_clamped(self) -> None:
        self.assertEqual(parse_cache_seconds({"latency_cache_seconds": "-1"}), 0.0)
        self.assertEqual(parse_cache_seconds({"latency_cache_seconds": "999"}), 300.0)
        self.assertEqual(parse_cache_seconds({"latency_cache_seconds": "bad"}), 30.0)

    def test_cached_latency_reuses_probe_result(self) -> None:
        settings = {"node_role": "single", "latency_cache_seconds": "30"}

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
