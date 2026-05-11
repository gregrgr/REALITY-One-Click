# API

The admin UI uses form posts, and subscription endpoints are stable URLs.

## Subscription

```text
GET /sub/{token}/clash.yaml
GET /sub/{token}/vless.txt
```

Both endpoints return `404` when the token is invalid or the user is disabled.

The Clash subscription is self-contained for local routing. It does not emit remote `rule-providers` or `GEOSITE` rules, so clients do not need to download `GeoSite.dat`; Claude/Anthropic, ChatGPT/OpenAI, and Figma domains are forced to `Proxy` before local direct rules, and the `Proxy` and `Final` groups do not include `DIRECT`; LAN/private ranges, local domains, `.cn`, common China handset/vendor service domains, ByteDance domains, NetEase domains, and `GEOIP,CN` are sent to `DIRECT`; unmatched TCP traffic goes to `Proxy`.

DNS leak prevention is included for Mihomo/Clash Meta clients: `tun.dns-hijack`, `strict-route`, `dns.respect-rules`, fake-ip, proxied DoH nameservers by default, exact and wildcard `nameserver-policy` entries for forced-proxy domains, domestic DoH policy for direct domains, and `#Proxy` DNS entries for forced-proxy domains. The profile also rejects UDP at rule level to prevent WebRTC/STUN/QUIC direct leaks because the VLESS REALITY node is TCP-only. Client-side features such as browser DoH, Android Private DNS, disabled TUN, or permissive browser WebRTC settings can still bypass the profile and should be turned off in the client environment.

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

Requires an authenticated admin session. In `single` mode the probe uses the server direct route. In `relay` mode it connects to `EGRESS_TAILSCALE_IP:EGRESS_BACKEND_PORT` as a SOCKS backend and then performs the external HTTP/TLS probe through the egress VPS, so the displayed latency is the relay-to-egress-to-Internet path rather than a local relay ping.

Example response:

```json
{
  "status": "ok",
  "node_role": "relay",
  "route": "relay-egress-socks",
  "backend": "100.64.10.20:10808",
  "backend_tcp_ms": 8,
  "exit_http_ms": 163,
  "exit_ip": "203.0.113.20",
  "probe_url": "https://www.gstatic.com/generate_204"
}
```
