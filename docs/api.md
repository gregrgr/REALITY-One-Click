# API

The admin UI uses form posts, and subscription endpoints are stable URLs.

## Subscription

```text
GET /sub/{token}/clash.yaml
GET /sub/{token}/vless.txt
```

Both endpoints return `404` when the token is invalid or the user is disabled.

The Clash subscription is self-contained for local routing. It does not emit remote `rule-providers` or `GEOSITE` rules, so clients do not need to download `GeoSite.dat`; Claude, ChatGPT/OpenAI, and Figma domains are forced to `Proxy` before local direct rules, and the `Proxy` group does not include `DIRECT`; LAN/private ranges, local domains, `.cn`, common China handset/vendor service domains, and `GEOIP,CN` are sent to `DIRECT`; unmatched traffic goes to the `Final` group, which defaults to `Proxy`. The VLESS REALITY proxy is a TCP profile and does not advertise UDP proxy support, so client UDP ping tests may time out.

DNS leak prevention is included for Mihomo/Clash Meta clients: `tun.dns-hijack`, `strict-route`, `dns.respect-rules`, fake-ip, proxied DoH nameservers by default, domestic DoH policy for direct domains, and `#Proxy` DNS entries for forced-proxy domains. Client-side features such as browser DoH, Android Private DNS, or disabled TUN can still bypass the profile and should be turned off in the client environment.

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
