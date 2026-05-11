from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

import yaml


CLASH_FORCE_PROXY_DOMAIN_SUFFIXES = [
    "anthropic.com",
    "anthropic.ai",
    "claude.ai",
    "claude.com",
    "claudeusercontent.com",
    "chatgpt.com",
    "openai.com",
    "oaistatic.com",
    "oaiusercontent.com",
    "openaiapi-site.azureedge.net",
    "openaicom.imgix.net",
    "figma.com",
    "figma.net",
    "figmausercontent.com",
    "figstatic.com",
]

CLASH_DOMESTIC_DNS = [
    "https://dns.alidns.com/dns-query",
    "https://doh.pub/dns-query",
]

CLASH_PROXY_DNS = [
    "https://1.1.1.1/dns-query#Proxy",
    "https://8.8.8.8/dns-query#Proxy",
]

CLASH_DIRECT_DOMAIN_SUFFIXES = [
    "cn",
    "allawnfs.com",
    "allawnos.com",
    "allawntech.com",
    "baidu.com",
    "baidubce.com",
    "bbk.com",
    "bcebos.com",
    "bdimg.com",
    "bdstatic.com",
    "coloros.com",
    "heytapmobile.com",
    "heytap.com",
    "heytapdownload.com",
    "heytapdl.com",
    "hicloud.com",
    "hihonor.com",
    "honor.cn",
    "huawei.com",
    "mi.com",
    "miui.com",
    "msftconnecttest.com",
    "msftncsi.com",
    "oppo.com",
    "vivo.com",
    "vivo.com.cn",
    "xiaomi.com",
    "amemv.com",
    "byteacctimg.com",
    "bytecdn.cn",
    "bytegoofy.com",
    "byteimg.com",
    "bytescm.com",
    "bytedance.com",
    "doubao.com",
    "douyin.com",
    "douyincdn.com",
    "douyinpic.com",
    "douyinstatic.com",
    "douyinvod.com",
    "feishu.cn",
    "feishu.net",
    "ibytedtos.com",
    "ibyteimg.com",
    "ixigua.com",
    "pstatp.com",
    "snssdk.com",
    "lcsc.com",
    "szlcsc.com",
    "toutiao.com",
    "toutiaocloud.com",
    "toutiaostatic.com",
    "toutiaovod.com",
    "volcengine.com",
    "volces.com",
    "zijieapi.com",
    "zijiecdn.com",
    "zijieimg.com",
    "126.com",
    "126.net",
    "127.net",
    "163.com",
    "163img.com",
    "163jiasu.com",
    "163yun.com",
    "icourse163.org",
    "netease.com",
    "netease.im",
    "neteasegame.com",
    "ntes53.com",
    "yeah.net",
    "ydstatic.com",
    "youdao.com",
]


CLASH_UDP_REJECT_RULES = [
    "NETWORK,UDP,REJECT",
]


CLASH_LOCAL_DIRECT_RULES = [
    "DOMAIN,localhost,DIRECT",
    "DOMAIN-SUFFIX,localhost,DIRECT",
    "DOMAIN-SUFFIX,local,DIRECT",
    "DOMAIN-SUFFIX,lan,DIRECT",
    "IP-CIDR,0.0.0.0/8,DIRECT,no-resolve",
    "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
    "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
    "IP-CIDR,169.254.0.0/16,DIRECT,no-resolve",
    "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
    "IP-CIDR,192.0.0.0/24,DIRECT,no-resolve",
    "IP-CIDR,192.0.2.0/24,DIRECT,no-resolve",
    "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
    "IP-CIDR,224.0.0.0/4,DIRECT,no-resolve",
    "IP-CIDR,240.0.0.0/4,DIRECT,no-resolve",
    "IP-CIDR6,::1/128,DIRECT,no-resolve",
    "IP-CIDR6,fc00::/7,DIRECT,no-resolve",
    "IP-CIDR6,fe80::/10,DIRECT,no-resolve",
    "GEOIP,CN,DIRECT,no-resolve",
]


def build_force_proxy_rules(group_name: str) -> list[str]:
    return [
        f"DOMAIN-SUFFIX,{domain},{group_name}"
        for domain in CLASH_FORCE_PROXY_DOMAIN_SUFFIXES
    ]


def build_direct_domain_rules() -> list[str]:
    return [
        f"DOMAIN-SUFFIX,{domain},DIRECT"
        for domain in CLASH_DIRECT_DOMAIN_SUFFIXES
    ]


def build_dns_policy() -> dict[str, list[str]]:
    policy: dict[str, list[str]] = {}
    for domain in CLASH_DIRECT_DOMAIN_SUFFIXES:
        policy[domain] = CLASH_DOMESTIC_DNS
        policy[f"+.{domain}"] = CLASH_DOMESTIC_DNS
    for domain in CLASH_FORCE_PROXY_DOMAIN_SUFFIXES:
        policy[domain] = CLASH_PROXY_DNS
        policy[f"+.{domain}"] = CLASH_PROXY_DNS
    return policy


def ensure_client_subscription_role(settings: dict[str, str]) -> None:
    if settings.get("node_role", "single") == "egress":
        raise ValueError("egress node does not provide client subscriptions.")


def build_proxy(settings: dict[str, str], user: Any) -> dict[str, Any]:
    ensure_client_subscription_role(settings)
    name = settings.get("node_name", "vps-reality-01")
    return {
        "name": name,
        "type": "vless",
        "server": settings.get("public_host", settings.get("panel_domain", "localhost")),
        "port": int(settings.get("public_port", "443")),
        "uuid": user["uuid"],
        "network": "tcp",
        "tls": True,
        "udp": False,
        "flow": "xtls-rprx-vision",
        "servername": settings.get("reality_server_name", "www.microsoft.com"),
        "client-fingerprint": settings.get("reality_fingerprint", "chrome"),
        "reality-opts": {
            "public-key": settings["reality_public_key"],
            "short-id": settings["reality_short_id"],
        },
    }


def clash_yaml(settings: dict[str, str], user: Any) -> str:
    ensure_client_subscription_role(settings)
    proxy = build_proxy(settings, user)
    group_name = "Proxy"
    direct_group = "Local"
    final_group = "Final"
    data = {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "find-process-mode": "strict",
        "tun": {
            "enable": True,
            "stack": "system",
            "auto-route": True,
            "auto-detect-interface": True,
            "strict-route": True,
            "dns-hijack": [
                "any:53",
                "tcp://any:53",
            ],
        },
        "dns": {
            "enable": True,
            "cache-algorithm": "arc",
            "listen": "0.0.0.0:1053",
            "ipv6": False,
            "use-hosts": True,
            "use-system-hosts": False,
            "respect-rules": True,
            "default-nameserver": [
                "223.5.5.5",
                "119.29.29.29",
            ],
            "enhanced-mode": "fake-ip",
            "fake-ip-range": "198.18.0.1/16",
            "fake-ip-filter-mode": "blacklist",
            "fake-ip-filter": [
                "*.lan",
                "*.local",
                "localhost",
                "router.asus.com",
                "connect.rom.miui.com",
                "localhost.ptlogin2.qq.com",
            ],
            "nameserver-policy": build_dns_policy(),
            "proxy-server-nameserver": CLASH_DOMESTIC_DNS,
            "direct-nameserver": CLASH_DOMESTIC_DNS,
            "direct-nameserver-follow-policy": True,
            "nameserver": CLASH_PROXY_DNS,
            "fallback": CLASH_PROXY_DNS,
            "fallback-filter": {
                "geoip": True,
                "geoip-code": "CN",
                "domain": [
                    f"+.{domain}"
                    for domain in CLASH_FORCE_PROXY_DOMAIN_SUFFIXES
                ],
            },
        },
        "proxies": [proxy],
        "proxy-groups": [
            {
                "name": group_name,
                "type": "select",
                "proxies": [proxy["name"]],
            },
            {
                "name": direct_group,
                "type": "select",
                "proxies": ["DIRECT", proxy["name"]],
            },
            {
                "name": final_group,
                "type": "select",
                "proxies": [group_name],
            },
        ],
        "rules": [
            *CLASH_UDP_REJECT_RULES,
            *build_force_proxy_rules(group_name),
            *build_direct_domain_rules(),
            *CLASH_LOCAL_DIRECT_RULES,
            f"MATCH,{final_group}",
        ],
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def vless_uri(settings: dict[str, str], user: Any) -> str:
    ensure_client_subscription_role(settings)
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
