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

