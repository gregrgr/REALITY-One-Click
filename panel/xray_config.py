from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_xray_config(settings: dict[str, str], users: list[Any]) -> dict[str, Any]:
    listen = settings.get("xray_listen", "127.0.0.1")
    port = int(settings.get("xray_port", "1443"))
    reality_dest = settings.get("reality_dest", "www.microsoft.com:443")
    reality_server_name = settings.get("reality_server_name", "www.microsoft.com")
    spider_x = settings.get("reality_spider_x", "/")

    clients = [
        {
            "id": user["uuid"],
            "email": user["name"],
            "flow": "xtls-rprx-vision",
        }
        for user in users
        if int(user["enabled"]) == 1
    ]

    return {
        "log": {
            "loglevel": "warning",
        },
        "inbounds": [
            {
                "tag": "vless-reality",
                "listen": listen,
                "port": port,
                "protocol": "vless",
                "settings": {
                    "clients": clients,
                    "decryption": "none",
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "dest": reality_dest,
                        "xver": 0,
                        "serverNames": [reality_server_name],
                        "privateKey": settings["reality_private_key"],
                        "shortIds": [settings["reality_short_id"]],
                        "spiderX": spider_x,
                    },
                },
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls", "quic"],
                },
            }
        ],
        "outbounds": [
            {
                "tag": "direct",
                "protocol": "freedom",
            },
            {
                "tag": "blocked",
                "protocol": "blackhole",
            },
        ],
    }


def write_xray_config(path: str, settings: dict[str, str], users: list[Any]) -> None:
    config = build_xray_config(settings, users)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

