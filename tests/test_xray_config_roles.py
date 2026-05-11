from __future__ import annotations

import json
import unittest

from panel.subscriptions import clash_yaml, vless_uri
from panel.xray_config import build_xray_config


BASE_SETTINGS = {
    "panel_domain": "panel.example.com",
    "node_name": "relay-node",
    "public_host": "relay.example.com",
    "public_port": "443",
    "panel_https_port": "8443",
    "xray_listen": "0.0.0.0",
    "xray_port": "443",
    "xray_api_host": "127.0.0.1",
    "xray_api_port": "10085",
    "reality_dest": "www.microsoft.com:443",
    "reality_server_name": "www.microsoft.com",
    "reality_private_key": "private-key",
    "reality_public_key": "public-key",
    "reality_short_id": "0123456789abcdef",
    "reality_spider_x": "/",
    "reality_fingerprint": "chrome",
}

USER = {
    "name": "alice",
    "uuid": "00000000-0000-0000-0000-000000000001",
    "enabled": 1,
}


def by_tag(items: list[dict], tag: str) -> dict:
    for item in items:
        if item.get("tag") == tag:
            return item
    raise AssertionError(f"tag not found: {tag}")


class XrayConfigRolesTest(unittest.TestCase):
    def test_single_role_backward_compatible(self) -> None:
        config = build_xray_config(BASE_SETTINGS, [USER])

        self.assertEqual(by_tag(config["inbounds"], "vless-reality")["protocol"], "vless")
        self.assertEqual(by_tag(config["outbounds"], "direct")["protocol"], "freedom")
        self.assertEqual(by_tag(config["outbounds"], "blocked")["protocol"], "blackhole")
        self.assertEqual(config["api"]["services"], ["StatsService"])

    def test_relay_role_has_socks_outbound(self) -> None:
        settings = {
            **BASE_SETTINGS,
            "node_role": "relay",
            "egress_tailscale_ip": "100.64.10.20",
            "egress_backend_port": "10808",
            "egress_backend_protocol": "socks",
        }

        config = build_xray_config(settings, [USER])
        outbound = by_tag(config["outbounds"], "egress-via-tailscale")
        server = outbound["settings"]["servers"][0]

        self.assertEqual(outbound["protocol"], "socks")
        self.assertEqual(server["address"], "100.64.10.20")
        self.assertEqual(server["port"], 10808)
        self.assertTrue(
            any(
                rule.get("inboundTag") == ["vless-reality"]
                and rule.get("outboundTag") == "egress-via-tailscale"
                for rule in config["routing"]["rules"]
            )
        )

    def test_relay_subscription_does_not_leak_egress_ip(self) -> None:
        settings = {
            **BASE_SETTINGS,
            "node_role": "relay",
            "egress_tailscale_ip": "100.64.10.20",
            "egress_backend_port": "10808",
        }

        clash = clash_yaml(settings, USER)
        uri = vless_uri(settings, USER)

        self.assertNotIn("100.64.10.20", clash)
        self.assertNotIn("100.64.10.20", uri)
        self.assertNotIn("100.", clash)
        self.assertIn("server: relay.example.com", clash)
        self.assertTrue(uri.startswith(f"vless://{USER['uuid']}@relay.example.com:443?"))

    def test_egress_role_bind_tailscale_only(self) -> None:
        settings = {
            "node_role": "egress",
            "egress_backend_listen": "100.64.10.20",
            "egress_backend_port": "10808",
            "egress_backend_protocol": "socks",
        }

        config = build_xray_config(settings, [])
        inbound = config["inbounds"][0]

        self.assertEqual([item["tag"] for item in config["inbounds"]], ["egress-socks-in"])
        self.assertNotEqual(inbound["listen"], "0.0.0.0")
        self.assertEqual(inbound["listen"], "100.64.10.20")
        self.assertEqual(inbound["port"], 10808)
        self.assertEqual(by_tag(config["outbounds"], "direct")["protocol"], "freedom")

    def test_egress_role_no_reality(self) -> None:
        settings = {
            "node_role": "egress",
            "egress_backend_listen": "100.64.10.20",
            "egress_backend_port": "10808",
        }

        payload = json.dumps(build_xray_config(settings, []))
        self.assertNotIn("realitySettings", payload)
        self.assertNotIn("vless-reality", payload)

    def test_egress_subscription_error(self) -> None:
        settings = {"node_role": "egress"}
        with self.assertRaisesRegex(ValueError, "egress node does not provide client subscriptions"):
            clash_yaml(settings, USER)


if __name__ == "__main__":
    unittest.main()
