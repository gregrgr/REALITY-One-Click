#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Please run as root." >&2
  exit 1
fi

echo "This will remove proxy-panel files and stop related services."
read -r -p "Continue? [y/N] " answer
case "$answer" in
  y|Y|yes|YES) ;;
  *) echo "Aborted."; exit 0 ;;
esac

systemctl disable --now proxy-panel 2>/dev/null || true
systemctl stop xray 2>/dev/null || true

rm -f /etc/systemd/system/proxy-panel.service
rm -f /etc/nginx/sites-enabled/proxy-panel.conf
rm -f /etc/nginx/sites-available/proxy-panel.conf
rm -f /etc/nginx/stream-conf.d/reality.conf
rm -f /etc/letsencrypt/renewal-hooks/deploy/proxy-panel-nginx-reload.sh
rm -f /usr/local/bin/proxy-panel

rm -rf /opt/proxy-panel
rm -rf /etc/proxy-panel
rm -rf /var/log/proxy-panel

systemctl daemon-reload
systemctl reload nginx 2>/dev/null || true

echo "Removed proxy-panel. Xray package and certificates were left in place."
