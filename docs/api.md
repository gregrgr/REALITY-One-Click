# API

The admin UI uses form posts, and subscription endpoints are stable URLs.

## Subscription

```text
GET /sub/{token}/clash.yaml
GET /sub/{token}/vless.txt
```

Both endpoints return `404` when the token is invalid or the user is disabled.

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
