# Two VPS Relay / Egress Mode

This project defaults to the existing single VPS mode. Two VPS mode keeps the public client entry on a relay VPS and sends proxied traffic to an egress VPS over Tailscale at the Xray application layer.

```text
Client
  |
  | VLESS REALITY
  v
Relay VPS
  |
  | Tailscale 100.x.x.x
  v
Egress VPS
  |
  | direct/freedom
  v
Internet
```

## Roles

- `NODE_ROLE=single`: existing behavior. Installs Xray REALITY, Nginx, certificate, panel, subscriptions, and UFW rules.
- `NODE_ROLE=relay`: public client entry. Installs Xray REALITY, Nginx, certificate, panel, subscriptions, and routes VLESS traffic to the egress backend over Tailscale.
- `NODE_ROLE=egress`: private backend only. Installs Xray and UFW rules, binds a SOCKS inbound to the Tailscale IP, and sends traffic out with `freedom/direct`. It does not install Nginx, certificates, the panel, or subscriptions.

The relay does not enable a Tailscale exit node and does not change the system default route. Tailscale is only the encrypted private link between relay and egress.

## Deployment Order

1. Install and join Tailscale on both VPS nodes.
2. Deploy the egress VPS first.
3. Confirm the egress Tailscale IP, for example `100.x.x.x`.
4. Deploy the relay VPS with `EGRESS_TAILSCALE_IP` set to the egress Tailscale IP.
5. Import the subscription from the relay panel.

## Egress Deployment

Run on the egress VPS:

```bash
NODE_ROLE=egress \
EGRESS_BACKEND_PORT=10808 \
SSH_PORT=22 \
bash install.sh --assume-yes
```

`EGRESS_BACKEND_LISTEN` is optional. When empty, the installer detects the `tailscale0` IPv4 address. It must be a `100.x.x.x` address and must not be `0.0.0.0`.

Validate:

```bash
bash scripts/validate_two_vps.sh egress
ss -lntp | grep 10808
```

## Relay Deployment

Run on the relay VPS:

```bash
NODE_ROLE=relay \
PANEL_DOMAIN=panel.example.com \
ACME_EMAIL=admin@example.com \
ADMIN_USER=admin \
ADMIN_PASSWORD='change-this-password' \
PUBLIC_HOST=relay.example.com \
XRAY_PUBLIC_PORT=443 \
XRAY_LISTEN=0.0.0.0 \
XRAY_PORT=443 \
EGRESS_TAILSCALE_IP=100.x.x.x \
EGRESS_BACKEND_PORT=10808 \
bash install.sh --assume-yes
```

Validate:

```bash
bash scripts/validate_two_vps.sh relay
```

## What Clients See

Clients only connect to the relay:

```text
relay public host:443
```

Subscriptions never include `EGRESS_TAILSCALE_IP`, `EGRESS_BACKEND_PORT`, or any `100.x.x.x` backend address. The final Internet-facing IP should be the egress VPS public IP.

## Firewall Model

Relay:

- allow SSH
- allow `XRAY_PUBLIC_PORT/tcp`, usually `443/tcp`
- allow `80/tcp` and `PANEL_HTTPS_PORT/tcp` for panel and subscription
- do not open `EGRESS_BACKEND_PORT`

Egress:

- allow SSH
- allow `EGRESS_BACKEND_PORT/tcp` only on `tailscale0`
- deny public access to `EGRESS_BACKEND_PORT/tcp`
- do not open public `443/tcp` unless you explicitly need it for another service

## Troubleshooting

### Relay Cannot Connect to Egress 10808

Check from relay:

```bash
tailscale status
ping -c 2 100.x.x.x
nc -vz 100.x.x.x 10808
```

Check on egress:

```bash
ss -lntp | grep 10808
ufw status verbose
journalctl -u xray -n 100 --no-pager
```

### Egress Listens on 0.0.0.0

This is unsafe and should fail validation. Fix the listen IP:

```bash
EGRESS_BACKEND_LISTEN=$(ip -4 addr show tailscale0 | awk '/inet / { sub(/\/.*/, "", $2); print $2; exit }')
sed -i "s#^EGRESS_BACKEND_LISTEN=.*#EGRESS_BACKEND_LISTEN=${EGRESS_BACKEND_LISTEN}#" /etc/proxy-panel/panel.env
proxy-panel render 2>/dev/null || true
systemctl restart xray
```

For egress-only installs without panel CLI, rerun:

```bash
NODE_ROLE=egress EGRESS_BACKEND_LISTEN="${EGRESS_BACKEND_LISTEN}" bash install.sh --assume-yes
```

### Client Connects but Exit IP Is Still Relay

On relay, confirm VLESS traffic routes to the egress outbound:

```bash
jq '.routing.rules' /usr/local/etc/xray/config.json
jq '.outbounds[] | select(.tag=="egress-via-tailscale")' /usr/local/etc/xray/config.json
```

The relay should not use Tailscale exit node:

```bash
tailscale debug prefs --json | jq '.ExitNodeID,.ExitNodeIP'
```

### Tailscale Uses DERP and Latency Is High

Check:

```bash
tailscale status
tailscale netcheck
```

Open/allow UDP for direct Tailscale peer paths according to Tailscale guidance, or choose VPS locations with better peer connectivity.

### UFW Locks SSH

Use your VPS provider console and allow your SSH port:

```bash
ufw allow 22/tcp
ufw reload
ufw status numbered
```

Replace `22` with your configured `SSH_PORT`.

### Subscription Leaks 100.x.x.x

On relay:

```bash
curl -ks https://panel.example.com:8443/sub/<token>/clash.yaml | grep -E '100\.|10808|egress'
curl -ks https://panel.example.com:8443/sub/<token>/vless.txt | grep -E '100\.|10808|egress'
```

There should be no output. If there is, check panel settings:

```bash
sqlite3 /var/lib/proxy-panel/panel.db "select key,value from settings where key like 'egress_%' or key in ('public_host','public_port','node_role');"
```
