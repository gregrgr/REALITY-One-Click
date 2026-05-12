from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def require_setting(settings: dict[str, str], key: str) -> str:
    value = settings.get(key, "")
    if not value:
        raise ValueError(f"{key} is required")
    return value


def direct_outbound() -> dict[str, Any]:
    return {
        "tag": "direct",
        "protocol": "freedom",
    }


def blocked_outbound() -> dict[str, Any]:
    return {
        "tag": "blocked",
        "protocol": "blackhole",
    }


def build_reality_inbound(settings: dict[str, str], users: list[Any]) -> dict[str, Any]:
    listen = settings.get("xray_listen", "0.0.0.0")
    port = int(settings.get("xray_port", "443"))
    reality_dest = settings.get("reality_dest", "www.microsoft.com:443")
    reality_server_name = settings.get("reality_server_name", "www.microsoft.com")
    spider_x = settings.get("reality_spider_x", "/")

    clients = [
        {
            "id": user["uuid"],
            "email": user["name"],
            "flow": "xtls-rprx-vision",
            "level": 0,
        }
        for user in users
        if int(user["enabled"]) == 1
    ]

    return {
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
                "privateKey": require_setting(settings, "reality_private_key"),
                "shortIds": [require_setting(settings, "reality_short_id")],
                "spiderX": spider_x,
            },
        },
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic"],
        },
    }


def build_api_inbound(settings: dict[str, str]) -> dict[str, Any]:
    api_host = settings.get("xray_api_host", "127.0.0.1")
    api_port = int(settings.get("xray_api_port", "10085"))
    return {
        "tag": "api",
        "listen": api_host,
        "port": api_port,
        "protocol": "dokodemo-door",
        "settings": {
            "address": api_host,
        },
    }


def build_xray_config(settings: dict[str, str], users: list[Any]) -> dict[str, Any]:
    return {
        "log": {
            "loglevel": "warning",
        },
        "inbounds": [
            build_reality_inbound(settings, users),
            build_api_inbound(settings),
        ],
        "routing": {
            "rules": [
                {
                    "type": "field",
                    "inboundTag": ["api"],
                    "outboundTag": "api",
                }
            ]
        },
        "outbounds": [
            direct_outbound(),
            blocked_outbound(),
        ],
        "api": {
            "tag": "api",
            "services": ["StatsService"],
        },
        "policy": {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True,
                }
            },
        },
        "stats": {},
    }


def write_xray_config(path: str, settings: dict[str, str], users: list[Any]) -> None:
    config = build_xray_config(settings, users)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
