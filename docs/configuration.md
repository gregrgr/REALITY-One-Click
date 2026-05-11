# Configuration

The installer stores runtime values in two places:

- `/etc/proxy-panel/panel.env`: service environment and bootstrap values.
- `/var/lib/proxy-panel/panel.db`: users, subscription tokens, and node settings.

The generated Xray configuration is written to `/usr/local/etc/xray/config.json`, matching the default path used by the official Xray install service.

## Important Settings

| Key | Purpose |
| --- | --- |
| `node_role` / `NODE_ROLE` | Node role: `single`, `relay`, or `egress`. Defaults to `single`. |
| `panel_domain` | HTTPS domain for the admin panel and subscriptions. |
| `panel_https_port` | HTTPS port for the admin panel and subscriptions. Defaults to `8443`. |
| `public_host` | Host or IP clients connect to. Defaults to the auto-detected public IPv4, falling back to `panel_domain`. |
| `public_port` | Public client port. Defaults to `443`. |
| `xray_listen` | Xray REALITY listen address. Defaults to `0.0.0.0`. |
| `xray_port` | Xray REALITY listen port. Defaults to `443`. |
| `xray_api_host` | Local Xray API host for traffic statistics. Defaults to `127.0.0.1`. |
| `xray_api_port` | Local Xray API port for traffic statistics. Defaults to `10085`. |
| `ssh_port` / `SSH_PORT` | SSH port to allow in UFW and list in cloud security group guidance. Defaults to `22`; it does not modify sshd. |
| `egress_tailscale_ip` / `EGRESS_TAILSCALE_IP` | Relay mode target egress Tailscale IPv4, for example `100.x.x.x`. Required for `NODE_ROLE=relay`. |
| `egress_backend_port` / `EGRESS_BACKEND_PORT` | Egress backend SOCKS port. Defaults to `10808`. |
| `egress_backend_listen` / `EGRESS_BACKEND_LISTEN` | Egress mode bind address. Defaults to the detected `tailscale0` `100.x.x.x` address. Must not be `0.0.0.0`. |
| `egress_backend_protocol` / `EGRESS_BACKEND_PROTOCOL` | Backend protocol between relay and egress. Defaults to `socks`; only `socks` is currently supported. |
| `tailscale_required` / `TAILSCALE_REQUIRED` | Require `tailscale status` to work for relay/egress. Defaults to `yes`. |
| `latency_probe_url` / `LATENCY_PROBE_URL` | URL used by the panel exit latency probe. Defaults to `https://www.gstatic.com/generate_204`. Relay mode probes through the egress SOCKS backend. |
| `latency_ip_check_url` / `LATENCY_IP_CHECK_URL` | URL used to detect the public exit IP shown in the panel. Defaults to `https://api.ipify.org`. |
| `latency_timeout_seconds` / `LATENCY_TIMEOUT_SECONDS` | Per-step timeout for panel latency checks. Defaults to `5`, clamped between `1` and `30`. |
| `latency_cache_seconds` / `LATENCY_CACHE_SECONDS` | Cache TTL for the panel `/api/latency` result. Defaults to `30`, clamped between `0` and `300`. Use `0` to disable caching. |
| `reality_dest` | REALITY camouflage destination, for example `www.microsoft.com:443`. |
| `reality_server_name` | TLS SNI used by clients for REALITY. |
| `reality_public_key` | Public key used by clients. |
| `reality_short_id` | REALITY short id used by clients. |

## Certificates

The installer supports two ACME modes:

```bash
ACME_CHALLENGE=http bash install.sh
```

or Cloudflare DNS API:

```bash
ACME_CHALLENGE=cloudflare \
CLOUDFLARE_API_TOKEN='cf-token-with-zone-dns-edit' \
bash install.sh
```

The Cloudflare token is written to `/etc/letsencrypt/cloudflare.ini` with `0600` permissions and is not stored in the panel database.

## Traffic Statistics

Traffic statistics are read from Xray StatsService through the local API inbound. The generated Xray config enables:

- `StatsService`
- per-user uplink/downlink counters
- local API inbound on `xray_api_host:xray_api_port`

Counters are held by Xray and reset when Xray restarts or when an admin uses the reset action:

```bash
proxy-panel traffic
proxy-panel reset-traffic
```

After changing settings, run:

```bash
proxy-panel render
systemctl restart xray
```

The admin panel URL includes the panel port:

```text
https://panel.example.com:8443
```

The proxy entry remains:

```text
<vps-public-ip>:443
```

To force a specific proxy address:

```bash
PUBLIC_HOST=203.0.113.10 bash install.sh
```
