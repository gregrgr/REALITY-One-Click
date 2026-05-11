from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from panel.database import Database
from panel.subscriptions import clash_yaml, vless_uri
from panel.traffic import human_bytes, parse_stats_output, parse_user_stats
from panel.xray_config import write_xray_config


SETTINGS = {
    "panel_domain": "panel.example.com",
    "node_name": "test-node",
    "public_host": "panel.example.com",
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


class PanelCoreTest(unittest.TestCase):
    def test_database_user_and_subscriptions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Database(str(Path(tmp) / "panel.db"))
            database.init()
            database.set_settings(SETTINGS)
            user = database.create_user("alice")

            clash = yaml.safe_load(clash_yaml(database.get_settings(), user))
            proxy = clash["proxies"][0]
            self.assertEqual(proxy["type"], "vless")
            self.assertEqual(proxy["server"], "panel.example.com")
            self.assertFalse(proxy["udp"])
            self.assertEqual(proxy["servername"], "www.microsoft.com")
            self.assertEqual(proxy["reality-opts"]["public-key"], "public-key")
            self.assertIn("rule-providers", clash)
            self.assertEqual(clash["rule-providers"]["direct"]["behavior"], "domain")
            self.assertEqual(clash["rule-providers"]["cncidr"]["behavior"], "ipcidr")
            self.assertEqual(clash["rule-providers"]["applications"]["behavior"], "classical")
            self.assertEqual(
                clash["rule-providers"]["direct"]["url"],
                "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/direct.txt",
            )
            self.assertIn("DOMAIN-SUFFIX,claude.ai,Proxy", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,anthropic.com,Proxy", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,claudeusercontent.com,Proxy", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,chatgpt.com,Proxy", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,openai.com,Proxy", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,figma.com,Proxy", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,cn,DIRECT", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,allawntech.com,DIRECT", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,bytedance.com,DIRECT", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,byteimg.com,DIRECT", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,163.com,DIRECT", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,netease.com,DIRECT", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,baidu.com,DIRECT", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,bdstatic.com,DIRECT", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,heytapdownload.com,DIRECT", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,allawnos.com,DIRECT", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,szlcsc.com,DIRECT", clash["rules"])
            self.assertIn("DOMAIN-SUFFIX,msftconnecttest.com,DIRECT", clash["rules"])
            self.assertIn("GEOIP,CN,DIRECT,no-resolve", clash["rules"])
            self.assertIn("RULE-SET,reject,REJECT", clash["rules"])
            self.assertIn("RULE-SET,direct,DIRECT", clash["rules"])
            self.assertIn("RULE-SET,cncidr,DIRECT", clash["rules"])
            self.assertIn("RULE-SET,proxy,Proxy", clash["rules"])
            self.assertIn("RULE-SET,gfw,Proxy", clash["rules"])
            self.assertIn("RULE-SET,tld-not-cn,Proxy", clash["rules"])
            self.assertIn("RULE-SET,telegramcidr,Proxy", clash["rules"])
            self.assertEqual(clash["rules"][0], "NETWORK,UDP,REJECT")
            self.assertFalse(any(rule.startswith("GEOSITE,") for rule in clash["rules"]))
            self.assertLess(
                clash["rules"].index("DOMAIN-SUFFIX,chatgpt.com,Proxy"),
                clash["rules"].index("RULE-SET,direct,DIRECT"),
            )
            self.assertLess(
                clash["rules"].index("RULE-SET,direct,DIRECT"),
                clash["rules"].index("RULE-SET,proxy,Proxy"),
            )
            self.assertLess(
                clash["rules"].index("RULE-SET,cncidr,DIRECT"),
                clash["rules"].index("GEOIP,CN,DIRECT,no-resolve"),
            )
            self.assertEqual(clash["rules"][-1], "MATCH,Final")
            self.assertIn("dns", clash)
            self.assertEqual(clash["tun"]["dns-hijack"], ["any:53", "tcp://any:53"])
            self.assertTrue(clash["tun"]["strict-route"])
            self.assertTrue(clash["dns"]["respect-rules"])
            self.assertEqual(clash["dns"]["use-system-hosts"], False)
            self.assertIn("#Proxy", clash["dns"]["nameserver-policy"]["+.chatgpt.com"][0])
            self.assertIn("#Proxy", clash["dns"]["nameserver-policy"]["anthropic.com"][0])
            self.assertIn("#Proxy", clash["dns"]["nameserver-policy"]["+.anthropic.com"][0])
            self.assertEqual(clash["dns"]["nameserver-policy"]["+.cn"][0], "https://dns.alidns.com/dns-query")
            self.assertEqual(clash["dns"]["nameserver-policy"]["bytedance.com"][0], "https://dns.alidns.com/dns-query")
            self.assertEqual(clash["dns"]["nameserver-policy"]["+.netease.com"][0], "https://dns.alidns.com/dns-query")
            self.assertEqual(clash["dns"]["nameserver-policy"]["baidu.com"][0], "https://dns.alidns.com/dns-query")
            self.assertEqual(clash["dns"]["nameserver-policy"]["+.allawnos.com"][0], "https://dns.alidns.com/dns-query")
            self.assertIn("#Proxy", clash["dns"]["nameserver"][0])
            self.assertIn("+.claude.ai", clash["dns"]["fallback-filter"]["domain"])
            self.assertNotIn("geosite", clash["dns"]["fallback-filter"])
            self.assertFalse(any(key.startswith("geosite:") for key in clash["dns"]["nameserver-policy"]))
            self.assertEqual(clash["dns"]["proxy-server-nameserver"][0], "https://dns.alidns.com/dns-query")
            proxy_group = next(group for group in clash["proxy-groups"] if group["name"] == "Proxy")
            self.assertNotIn("DIRECT", proxy_group["proxies"])
            final_group = next(group for group in clash["proxy-groups"] if group["name"] == "Final")
            self.assertNotIn("DIRECT", final_group["proxies"])

            uri = vless_uri(database.get_settings(), user)
            self.assertTrue(uri.startswith(f"vless://{user['uuid']}@panel.example.com:443?"))
            self.assertIn("security=reality", uri)
            self.assertIn("pbk=public-key", uri)

    def test_clash_rule_providers_can_be_disabled(self) -> None:
        user = {"uuid": "00000000-0000-0000-0000-000000000001", "name": "alice"}
        clash = yaml.safe_load(clash_yaml({**SETTINGS, "clash_rule_providers_enabled": "no"}, user))

        self.assertNotIn("rule-providers", clash)
        self.assertFalse(any(rule.startswith("RULE-SET,") for rule in clash["rules"]))
        self.assertIn("DOMAIN-SUFFIX,anthropic.com,Proxy", clash["rules"])
        self.assertEqual(clash["rules"][0], "NETWORK,UDP,REJECT")

    def test_xray_config_contains_enabled_users_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Database(str(Path(tmp) / "panel.db"))
            database.init()
            database.set_settings(SETTINGS)
            alice = database.create_user("alice")
            bob = database.create_user("bob")
            database.set_user_enabled(bob["id"], False)

            config_path = Path(tmp) / "config.json"
            write_xray_config(str(config_path), database.get_settings(), database.enabled_users())

            data = json.loads(config_path.read_text(encoding="utf-8"))
            inbound = data["inbounds"][0]
            clients = inbound["settings"]["clients"]
            self.assertEqual([client["id"] for client in clients], [alice["uuid"]])
            self.assertEqual(inbound["streamSettings"]["security"], "reality")
            self.assertEqual(
                inbound["streamSettings"]["realitySettings"]["shortIds"],
                ["0123456789abcdef"],
            )
            self.assertIn("stats", data)
            self.assertEqual(data["api"]["services"], ["StatsService"])
            self.assertEqual(data["inbounds"][1]["tag"], "api")
            self.assertNotIn("system", data["policy"])

    def test_traffic_parser(self) -> None:
        payload = """
        {
          "stat": [
            {"name": "user>>>alice>>>traffic>>>uplink", "value": 1024},
            {"name": "user>>>alice>>>traffic>>>downlink", "value": 2048}
          ]
        }
        """
        stats = parse_stats_output(payload)
        by_user = parse_user_stats(stats)
        self.assertEqual(by_user["alice"]["uplink"], 1024)
        self.assertEqual(by_user["alice"]["downlink"], 2048)
        self.assertEqual(human_bytes(2048), "2.0 KiB")


if __name__ == "__main__":
    unittest.main()
