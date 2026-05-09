from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

import yaml


def build_proxy(settings: dict[str, str], user: Any) -> dict[str, Any]:
    name = settings.get("node_name", "vps-reality-01")
    return {
        "name": name,
        "type": "vless",
        "server": settings.get("public_host", settings.get("panel_domain", "localhost")),
        "port": int(settings.get("public_port", "443")),
        "uuid": user["uuid"],
        "network": "tcp",
        "tls": True,
        "udp": True,
        "flow": "xtls-rprx-vision",
        "servername": settings.get("reality_server_name", "www.microsoft.com"),
        "client-fingerprint": settings.get("reality_fingerprint", "chrome"),
        "reality-opts": {
            "public-key": settings["reality_public_key"],
            "short-id": settings["reality_short_id"],
        },
    }


def clash_yaml(settings: dict[str, str], user: Any) -> str:
    proxy = build_proxy(settings, user)
    group_name = "Proxy"
    data = {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "proxies": [proxy],
        "proxy-groups": [
            {
                "name": group_name,
                "type": "select",
                "proxies": [proxy["name"], "DIRECT"],
            }
        ],
        "rules": [
            f"MATCH,{group_name}",
        ],
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def vless_uri(settings: dict[str, str], user: Any) -> str:
    host = settings.get("public_host", settings.get("panel_domain", "localhost"))
    port = settings.get("public_port", "443")
    params = {
        "encryption": "none",
        "flow": "xtls-rprx-vision",
        "security": "reality",
        "sni": settings.get("reality_server_name", "www.microsoft.com"),
        "fp": settings.get("reality_fingerprint", "chrome"),
        "pbk": settings["reality_public_key"],
        "sid": settings["reality_short_id"],
        "type": "tcp",
        "headerType": "none",
    }
    label = quote(settings.get("node_name", "vps-reality-01"))
    return f"vless://{user['uuid']}@{host}:{port}?{urlencode(params)}#{label}"
