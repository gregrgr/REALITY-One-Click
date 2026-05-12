# API

The admin UI uses form posts, and subscription endpoints are stable URLs.

## Subscription

```text
GET /sub/{token}/clash.yaml
GET /sub/{token}/vless.txt
```

Both endpoints return `404` when the token is invalid or the user is disabled.

The Clash subscription uses Loyalsoldier Clash `rule-providers` by default and does not emit `GEOSITE` rules, so clients do not need `GeoSite.dat`. A curated list of services (AI tools — Anthropic/OpenAI/HuggingFace, design — Figma, dev — GitHub, social — Twitter/X/Reddit/Discord, media — YouTube, knowledge/comms — Notion/Telegram web) is embedded before provider rules and forced to `Proxy`. The `Proxy` and `Final` groups do not include `DIRECT`. LAN/private ranges, local domains, `.cn`, common China handset/vendor service domains, Baidu, HeyTap/AllawnOS, LCSC, ByteDance domains, NetEase domains, Microsoft connectivity checks, Loyalsoldier `direct`/`cncidr`/`lancidr` rules, and `GEOIP,CN` are sent to `DIRECT`; Loyalsoldier `proxy`/`gfw`/`tld-not-cn`/`telegramcidr` rules and unmatched TCP traffic go to `Proxy`.

DNS leak prevention is included for Mihomo/Clash Meta clients: `tun.dns-hijack`, `strict-route`, `dns.respect-rules`, fake-ip, proxied DoH nameservers by default, exact and wildcard `nameserver-policy` entries for forced-proxy domains, domestic DoH policy for direct domains, and `#Proxy` DNS entries for forced-proxy domains. The Mihomo `sniffer` is enabled for 443/8443/80/8080/QUIC so that IP-only TLS connections still match domain rules. The profile also rejects UDP at rule level to prevent WebRTC/STUN/QUIC direct leaks because the VLESS REALITY node is TCP-only. Client-side features such as browser DoH, Android Private DNS, disabled TUN, or permissive browser WebRTC settings can still bypass the profile and should be turned off in the client environment.

## Status

```text
GET /api/status
```

Requires an authenticated admin session.

Example response:

```json
{
  "xray": "active",
  "nginx": "active",
  "proxy-panel": "active"
}
```

## Traffic

```text
GET /api/traffic
```

Requires an authenticated admin session.

Example response:

```json
{
  "alice": {
    "uplink": 1024,
    "downlink": 2048,
    "total": 3072
  }
}
```

## Exit Latency

```text
GET /api/latency
```

Requires an authenticated admin session. The probe uses the server's direct route to the configured `latency_probe_url` and `latency_ip_check_url` and reports HTTP latency plus the detected exit IP.

The panel caches this result for `LATENCY_CACHE_SECONDS` seconds, defaulting to `30`, to avoid repeatedly probing under frequent dashboard refreshes.

Example response:

```json
{
  "status": "ok",
  "route": "direct",
  "exit_http_ms": 45,
  "exit_ip": "203.0.113.10",
  "probe_url": "https://www.gstatic.com/generate_204"
}
```
