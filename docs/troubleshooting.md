# Troubleshooting

## Certificate Fails

Check that the panel domain points to the VPS and that port `80/tcp` is reachable:

```bash
dig +short panel.example.com
ss -lntp | grep ':80'
certbot certificates
```

## Panel Opens but Node Does Not Connect

Check the stream split and Xray status:

```bash
nginx -t
systemctl status nginx xray proxy-panel
journalctl -u xray -n 100 --no-pager
```

The client connection host is usually the panel domain, but the REALITY SNI must be the configured `reality_server_name`.

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
