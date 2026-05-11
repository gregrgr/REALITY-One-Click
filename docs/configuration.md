# Configuration

The installer stores runtime values in two places:

- `/etc/proxy-panel/panel.env`: service environment and bootstrap values.
- `/var/lib/proxy-panel/panel.db`: users, subscription tokens, and node settings.

The generated Xray configuration is written to `/etc/xray/config.json`.

## Important Settings

| Key | Purpose |
| --- | --- |
| `panel_domain` | HTTPS domain for the admin panel and subscriptions. |
| `panel_https_port` | HTTPS port for the admin panel and subscriptions. Defaults to `8443`. |
| `public_host` | Host or IP clients connect to. Defaults to `panel_domain`. |
| `public_port` | Public client port. Defaults to `443`. |
| `xray_listen` | Xray REALITY listen address. Defaults to `0.0.0.0`. |
| `xray_port` | Xray REALITY listen port. Defaults to `443`. |
| `xray_api_host` | Local Xray API host for traffic statistics. Defaults to `127.0.0.1`. |
| `xray_api_port` | Local Xray API port for traffic statistics. Defaults to `10085`. |
| `ssh_port` / `SSH_PORT` | SSH port to allow in UFW and list in cloud security group guidance. Defaults to `22`; it does not modify sshd. |
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
<proxy-domain>:443
```

To force a specific proxy address:

```bash
PUBLIC_HOST=proxy.example.com bash install.sh
```
