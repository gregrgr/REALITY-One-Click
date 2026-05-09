# Configuration

The installer stores runtime values in two places:

- `/etc/proxy-panel/panel.env`: service environment and bootstrap values.
- `/var/lib/proxy-panel/panel.db`: users, subscription tokens, and node settings.

The generated Xray configuration is written to `/etc/xray/config.json`.

## Important Settings

| Key | Purpose |
| --- | --- |
| `panel_domain` | HTTPS domain for the admin panel and subscriptions. |
| `public_host` | Hostname clients connect to. Defaults to `panel_domain`. |
| `public_port` | Public client port. Defaults to `443`. |
| `reality_dest` | REALITY camouflage destination, for example `www.microsoft.com:443`. |
| `reality_server_name` | TLS SNI used by clients for REALITY. |
| `reality_public_key` | Public key used by clients. |
| `reality_short_id` | REALITY short id used by clients. |

After changing settings, run:

```bash
proxy-panel render
systemctl restart xray
```

