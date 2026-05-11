from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def node_role(settings: dict[str, str]) -> str:
    role = settings.get("node_role", "single") or "single"
    if role not in {"single", "relay", "egress"}:
        raise ValueError(f"Unsupported node_role: {role}")
    return role


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


def with_stats(config: dict[str, Any]) -> dict[str, Any]:
    config.update(
        {
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
                "system": {
                    "statsInboundUplink": True,
                    "statsInboundDownlink": True,
                    "statsOutboundUplink": True,
                    "statsOutboundDownlink": True,
                },
            },
            "stats": {},
        }
    )
    return config


def build_single_config(settings: dict[str, str], users: list[Any]) -> dict[str, Any]:
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
    }


def build_relay_config(settings: dict[str, str], users: list[Any]) -> dict[str, Any]:
    if settings.get("egress_backend_protocol", "socks") != "socks":
        raise ValueError("Only egress_backend_protocol=socks is currently supported")

    config = {
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
                },
                {
                    "type": "field",
                    "inboundTag": ["vless-reality"],
                    "outboundTag": "egress-via-tailscale",
                },
            ]
        },
        "outbounds": [
            {
                "tag": "egress-via-tailscale",
                "protocol": "socks",
                "settings": {
                    "servers": [
                        {
                            "address": require_setting(settings, "egress_tailscale_ip"),
                            "port": int(settings.get("egress_backend_port", "10808")),
                        }
                    ]
                },
            },
            blocked_outbound(),
        ],
    }
    return with_stats(config)


def build_egress_config(settings: dict[str, str]) -> dict[str, Any]:
    if settings.get("egress_backend_protocol", "socks") != "socks":
        raise ValueError("Only egress_backend_protocol=socks is currently supported")

    listen = require_setting(settings, "egress_backend_listen")
    if listen == "0.0.0.0":
        raise ValueError("egress_backend_listen must not be 0.0.0.0")

    return {
        "log": {
            "loglevel": "warning",
        },
        "inbounds": [
            {
                "tag": "egress-socks-in",
                "listen": listen,
                "port": int(settings.get("egress_backend_port", "10808")),
                "protocol": "socks",
                "settings": {
                    "auth": "noauth",
                    "udp": False,
                },
            }
        ],
        "routing": {
            "rules": [
                {
                    "type": "field",
                    "inboundTag": ["egress-socks-in"],
                    "outboundTag": "direct",
                }
            ]
        },
        "outbounds": [
            direct_outbound(),
            blocked_outbound(),
        ],
    }


def build_xray_config(settings: dict[str, str], users: list[Any]) -> dict[str, Any]:
    role = node_role(settings)
    if role == "relay":
        return build_relay_config(settings, users)
    if role == "egress":
        return build_egress_config(settings)
    return with_stats(build_single_config(settings, users))


def write_xray_config(path: str, settings: dict[str, str], users: list[Any]) -> None:
    config = build_xray_config(settings, users)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
