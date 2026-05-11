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

The client connection host is usually the VPS public IP, but the REALITY SNI must be the configured `reality_server_name`.

Current default subscriptions use the VPS public IP as the proxy `server`, while the panel domain is used for the admin and subscription URL on port `8443`.

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
server: 203.0.113.10
servername: proxy.example.com
```

The `server` should be the VPS public IP, but `servername` must be a REALITY camouflage SNI such as:

```yaml
server: 203.0.113.10
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

## UDP Proxy Ping Timeout

The default node is VLESS + REALITY over TCP on `443/tcp`; it does not listen on `443/udp`.
Some clients show `UDP Proxy` or UDP ping checks, and those checks can time out even when normal TCP/HTTPS proxy traffic works.

Use TCP/HTTP latency checks for this profile. If the client still shows stale `udp: true`, refresh the subscription after updating the server.

Current subscriptions intentionally place `NETWORK,UDP,REJECT` before domain routing rules. This blocks WebRTC/STUN/QUIC from falling through to `DIRECT` when the TCP-only VLESS node cannot carry UDP. If a browser WebRTC leak test still shows a local or public IP, verify that the client is actually using the refreshed Clash profile, TUN mode is enabled, and browser-level WebRTC leak prevention is enabled.

The current default architecture gives Xray REALITY exclusive use of `443/tcp` and exposes the admin panel on `8443/tcp`. Remove old stream split config if it still exists:

```bash
rm -f /etc/nginx/stream-conf.d/reality.conf
nginx -t && systemctl reload nginx
systemctl restart xray
```

## Relay CPU Is 100%

First identify the process. On the relay VPS run:

```bash
bash scripts/diagnose_relay_cpu.sh
```

If `xray` is the top CPU process, check whether traffic is actually high:

```bash
proxy-panel traffic
ss -Hantp | awk '{print $5}' | sed 's/\[//;s/\]//' | sed 's/:[0-9]*$//' | sort | uniq -c | sort -nr | head
```

Relay mode still decrypts client REALITY traffic and forwards it to the egress SOCKS backend, so high throughput can saturate small VPS CPUs. Also confirm that clients have refreshed the latest subscription with `NETWORK,UDP,REJECT`; old client profiles can keep generating UDP/WebRTC/QUIC traffic.

If `proxy-panel` is the top CPU process, repeated dashboard latency checks may be involved. The panel caches `/api/latency` for `LATENCY_CACHE_SECONDS`, default `30`. Increase it if the dashboard is polled frequently:

```bash
sed -i 's#^LATENCY_CACHE_SECONDS=.*#LATENCY_CACHE_SECONDS=120#' /etc/proxy-panel/panel.env
systemctl restart proxy-panel
```

If `tailscaled` is the top CPU process, check whether relay-to-egress traffic is using DERP rather than a direct Tailscale path:

```bash
tailscale status
tailscale netcheck
```

DERP relay paths can raise latency and CPU. Prefer VPS regions/providers that can form direct UDP paths, and make sure provider firewalls do not block Tailscale UDP.

If `xray.service` is running but `443/tcp` is still not listening, check the config path used by systemd. The official Xray installer normally reads `/usr/local/etc/xray/config.json`, and the panel must render to the same file:

```bash
systemctl status xray --no-pager -l
grep '^PROXY_PANEL_CONFIG=' /etc/proxy-panel/panel.env
sed -i 's#^PROXY_PANEL_CONFIG=.*#PROXY_PANEL_CONFIG=/usr/local/etc/xray/config.json#' /etc/proxy-panel/panel.env
proxy-panel render
systemctl restart xray
ss -lntp | grep -E ':(443|10085)\b'
```

If clients report `216.36.x.x:443 i/o timeout` while the VPS shows Xray listening on `443/tcp`, the service is up but the client path is dropping packets. Check the cloud security group, VPS firewall, and client-side route:

```bash
# On the client router, if available:
nc -vz -w 5 <vps-public-ip> 443
traceroute -T -p 443 <vps-public-ip>

# On the VPS while the client retries:
tcpdump -ni any 'tcp port 443'
ufw status verbose
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
