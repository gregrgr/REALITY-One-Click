#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Please run as root." >&2
  exit 1
fi

if [[ -x /usr/local/bin/xray ]]; then
  echo "Upgrading Xray Core..."
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh -o "$tmp/install-release.sh"
  bash "$tmp/install-release.sh" install
fi

echo "Updating panel files..."
install -d -m 0755 /opt/proxy-panel
rm -rf /opt/proxy-panel/panel
cp -a "$ROOT_DIR/panel" /opt/proxy-panel/

/opt/proxy-panel/.venv/bin/pip install --upgrade -r /opt/proxy-panel/panel/requirements.txt
/opt/proxy-panel/.venv/bin/python -m panel.cli render

systemctl restart proxy-panel xray
echo "Upgrade complete."
