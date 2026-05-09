from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from panel.database import Database
from panel.subscriptions import clash_yaml, vless_uri
from panel.xray_config import write_xray_config


SETTINGS = {
    "panel_domain": "panel.example.com",
    "node_name": "test-node",
    "public_host": "panel.example.com",
    "public_port": "443",
    "xray_listen": "127.0.0.1",
    "xray_port": "1443",
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
            self.assertEqual(proxy["servername"], "www.microsoft.com")
            self.assertEqual(proxy["reality-opts"]["public-key"], "public-key")

            uri = vless_uri(database.get_settings(), user)
            self.assertTrue(uri.startswith(f"vless://{user['uuid']}@panel.example.com:443?"))
            self.assertIn("security=reality", uri)
            self.assertIn("pbk=public-key", uri)

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


if __name__ == "__main__":
    unittest.main()

