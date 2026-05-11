# Troubleshooting

## Certificate Fails

Check that the panel domain points to the VPS and that port `80/tcp` is reachable:

```bash
dig +short panel.example.com
ss -lntp | grep ':80'
certbot certificates
```

## Panel Opens but Node Does Not Connect

Check the panel port, proxy port, and service status:

```bash
nginx -t
ss -lntp | grep -E ':(443|8443|8080|10085)\b'
systemctl status nginx xray proxy-panel
journalctl -u xray -n 100 --no-pager
```

The client connection host is usually the panel domain, but the REALITY SNI must be the configured `reality_server_name`.

Current default subscriptions use the panel domain as the proxy `server`; the same domain serves the admin and subscription URL on port `8443`.

## TLS Handshake Failure on Port 443

If the client reports:

```text
proxy.example.com:443 connect error: remote error: tls: handshake failure
```

first check whether the Clash subscription is using the panel domain as REALITY SNI:

```bash
curl -ks https://proxy.example.com:8443/sub/<token>/clash.yaml | grep -E 'server:|servername:|reality-opts'
```

This is wrong:

```yaml
server: proxy.example.com
servername: proxy.example.com
```

The `server` should be your proxy domain, but `servername` must be a REALITY camouflage SNI such as:

```yaml
server: proxy.example.com
servername: www.microsoft.com
```

Fix the panel database and regenerate Xray config:

```bash
sqlite3 /var/lib/proxy-panel/panel.db \
  "UPDATE settings SET value='www.microsoft.com' WHERE key='reality_server_name';"
proxy-panel render
systemctl restart xray proxy-panel nginx
```

Then refresh the client subscription from the subscription server.

The current default architecture gives Xray REALITY exclusive use of `443/tcp` and exposes the admin panel on `8443/tcp`. Remove old stream split config if it still exists:

```bash
rm -f /etc/nginx/stream-conf.d/reality.conf
nginx -t && systemctl reload nginx
systemctl restart xray
```

## Regenerate Config

```bash
proxy-panel render
systemctl restart xray
```

## Cloudflare DNS Certificate

Check that the token can edit DNS records for the zone:

```bash
cat /etc/letsencrypt/cloudflare.ini
certbot certificates
journalctl -u certbot -n 100 --no-pager
```

The token file should contain only `dns_cloudflare_api_token = ...` and should have `0600` permissions.

## Traffic Statistics Are Zero

Traffic counters require the generated Xray API inbound and StatsService:

```bash
proxy-panel render
systemctl restart xray
proxy-panel traffic
```

Counters reset after Xray restarts.
