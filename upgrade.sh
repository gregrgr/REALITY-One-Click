#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=scripts/common.sh
source "$ROOT_DIR/scripts/common.sh"
# shellcheck source=scripts/install_xray.sh
source "$ROOT_DIR/scripts/install_xray.sh"
# shellcheck source=scripts/install_nginx.sh
source "$ROOT_DIR/scripts/install_nginx.sh"

load_panel_env() {
  if [[ -r "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi
}

upsert_env_key() {
  local key="$1"
  local value="$2"
  local tmp
  tmp="$(mktemp)"

  if [[ -r "$ENV_FILE" ]]; then
    awk -v key="$key" -v value="$value" '
      BEGIN { written = 0 }
      $0 ~ "^" key "=" {
        print key "=" value
        written = 1
        next
      }
      { print }
      END {
        if (!written) {
          print key "=" value
        }
      }
    ' "$ENV_FILE" > "$tmp"
  else
    printf '%s=%s\n' "$key" "$value" > "$tmp"
  fi

  install -D -m 0640 "$tmp" "$ENV_FILE"
  rm -f "$tmp"
}

normalize_direct_443_env() {
  install -d -m 0750 "$ETC_DIR"
  load_panel_env

  if [[ -z "${PANEL_DOMAIN:-}" ]]; then
    warn "PANEL_DOMAIN is missing in $ENV_FILE; skipping Nginx env migration."
  fi

  PROXY_PANEL_DB="${PROXY_PANEL_DB:-$DATA_DIR/panel.db}"
  PROXY_PANEL_CONFIG="${PROXY_PANEL_CONFIG:-/usr/local/etc/xray/config.json}"
  if [[ "$PROXY_PANEL_CONFIG" == "/etc/xray/config.json" ]]; then
    PROXY_PANEL_CONFIG="/usr/local/etc/xray/config.json"
  fi
  PROXY_PANEL_SECRET_KEY="${PROXY_PANEL_SECRET_KEY:-$(generate_password)}"
  NODE_ROLE="${NODE_ROLE:-single}"
  EGRESS_BACKEND_PORT="${EGRESS_BACKEND_PORT:-10808}"
  EGRESS_BACKEND_PROTOCOL="${EGRESS_BACKEND_PROTOCOL:-socks}"
  TAILSCALE_REQUIRED="${TAILSCALE_REQUIRED:-yes}"
  LATENCY_PROBE_URL="${LATENCY_PROBE_URL:-https://www.gstatic.com/generate_204}"
  LATENCY_IP_CHECK_URL="${LATENCY_IP_CHECK_URL:-https://api.ipify.org}"
  LATENCY_TIMEOUT_SECONDS="${LATENCY_TIMEOUT_SECONDS:-5}"
  PANEL_HTTPS_PORT="${PANEL_HTTPS_PORT:-8443}"
  XRAY_LISTEN="0.0.0.0"
  XRAY_PORT="443"
  XRAY_PUBLIC_PORT="443"
  validate_node_role
  if [[ "$NODE_ROLE" != "single" ]]; then
    require_tailscale_ready
  fi

  if [[ "$NODE_ROLE" == "egress" ]]; then
    validate_tailscale_bind_ip
  else
    local detected_public_host
    detected_public_host="$(detect_public_ipv4 || true)"
    if [[ -n "$detected_public_host" ]]; then
      PUBLIC_HOST="$detected_public_host"
    elif [[ -z "${PUBLIC_HOST:-}" && -n "${PANEL_DOMAIN:-}" ]]; then
      PUBLIC_HOST="$PANEL_DOMAIN"
      warn "Could not detect public IPv4; falling back PUBLIC_HOST to PANEL_DOMAIN."
    elif [[ -z "${PUBLIC_HOST:-}" ]]; then
      warn "Could not detect public IPv4 and PANEL_DOMAIN is missing; keeping PUBLIC_HOST unset."
      PUBLIC_HOST=""
    else
      warn "Could not detect public IPv4; keeping existing PUBLIC_HOST=$PUBLIC_HOST."
    fi
  fi

  if [[ -n "${PANEL_DOMAIN:-}" ]]; then
    PROXY_PANEL_PUBLIC_BASE="https://${PANEL_DOMAIN}:${PANEL_HTTPS_PORT}"
  else
    PROXY_PANEL_PUBLIC_BASE="${PROXY_PANEL_PUBLIC_BASE:-https://localhost:${PANEL_HTTPS_PORT}}"
  fi

  export PROXY_PANEL_DB PROXY_PANEL_CONFIG PROXY_PANEL_SECRET_KEY PROXY_PANEL_PUBLIC_BASE
  export NODE_ROLE EGRESS_TAILSCALE_IP EGRESS_BACKEND_PORT EGRESS_BACKEND_LISTEN
  export EGRESS_BACKEND_PROTOCOL TAILSCALE_REQUIRED
  export LATENCY_PROBE_URL LATENCY_IP_CHECK_URL LATENCY_TIMEOUT_SECONDS
  export PANEL_DOMAIN PANEL_HTTPS_PORT PUBLIC_HOST XRAY_LISTEN XRAY_PORT XRAY_PUBLIC_PORT

  upsert_env_key "PROXY_PANEL_DB" "$PROXY_PANEL_DB"
  upsert_env_key "PROXY_PANEL_CONFIG" "$PROXY_PANEL_CONFIG"
  upsert_env_key "PROXY_PANEL_SECRET_KEY" "$PROXY_PANEL_SECRET_KEY"
  upsert_env_key "PROXY_PANEL_PUBLIC_BASE" "$PROXY_PANEL_PUBLIC_BASE"
  upsert_env_key "NODE_ROLE" "$NODE_ROLE"
  upsert_env_key "PANEL_HTTPS_PORT" "$PANEL_HTTPS_PORT"
  upsert_env_key "PUBLIC_HOST" "${PUBLIC_HOST:-}"
  upsert_env_key "XRAY_PUBLIC_PORT" "$XRAY_PUBLIC_PORT"
  upsert_env_key "XRAY_LISTEN" "$XRAY_LISTEN"
  upsert_env_key "XRAY_PORT" "$XRAY_PORT"
  upsert_env_key "EGRESS_TAILSCALE_IP" "${EGRESS_TAILSCALE_IP:-}"
  upsert_env_key "EGRESS_BACKEND_PORT" "$EGRESS_BACKEND_PORT"
  upsert_env_key "EGRESS_BACKEND_LISTEN" "${EGRESS_BACKEND_LISTEN:-}"
  upsert_env_key "EGRESS_BACKEND_PROTOCOL" "$EGRESS_BACKEND_PROTOCOL"
  upsert_env_key "TAILSCALE_REQUIRED" "$TAILSCALE_REQUIRED"
  upsert_env_key "LATENCY_PROBE_URL" "$LATENCY_PROBE_URL"
  upsert_env_key "LATENCY_IP_CHECK_URL" "$LATENCY_IP_CHECK_URL"
  upsert_env_key "LATENCY_TIMEOUT_SECONDS" "$LATENCY_TIMEOUT_SECONDS"
}

sync_database_runtime_settings() {
  load_panel_env

  local setting_args=(
    --setting "node_role=${NODE_ROLE:-single}"
    --setting "panel_https_port=${PANEL_HTTPS_PORT:-8443}"
    --setting "public_port=${XRAY_PUBLIC_PORT:-443}"
    --setting "xray_listen=${XRAY_LISTEN:-0.0.0.0}"
    --setting "xray_port=${XRAY_PORT:-443}"
    --setting "egress_tailscale_ip=${EGRESS_TAILSCALE_IP:-}"
    --setting "egress_backend_port=${EGRESS_BACKEND_PORT:-10808}"
    --setting "egress_backend_protocol=${EGRESS_BACKEND_PROTOCOL:-socks}"
    --setting "latency_probe_url=${LATENCY_PROBE_URL:-https://www.gstatic.com/generate_204}"
    --setting "latency_ip_check_url=${LATENCY_IP_CHECK_URL:-https://api.ipify.org}"
    --setting "latency_timeout_seconds=${LATENCY_TIMEOUT_SECONDS:-5}"
  )

  if [[ -n "${PANEL_DOMAIN:-}" ]]; then
    setting_args+=(--setting "panel_domain=$PANEL_DOMAIN")
  fi
  if [[ -n "${PUBLIC_HOST:-}" ]]; then
    setting_args+=(--setting "public_host=$PUBLIC_HOST")
  fi

  "$OPT_DIR/.venv/bin/python" -m panel.cli set-settings "${setting_args[@]}"
}

render_upgrade_nginx_config() {
  load_panel_env
  if [[ -z "${PANEL_DOMAIN:-}" ]]; then
    warn "PANEL_DOMAIN is missing; skipped Nginx render."
    return
  fi

  install_nginx_base
  render_nginx_tls_config
  disable_nginx_stream_config
  reload_or_start_nginx
}

require_root

if [[ -x /usr/local/bin/xray ]]; then
  echo "Upgrading Xray Core..."
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh -o "$tmp/install-release.sh"
  bash "$tmp/install-release.sh" install
fi

normalize_direct_443_env

if [[ "${NODE_ROLE:-single}" == "relay" ]]; then
  require_relay_can_reach_egress
fi

if [[ "${NODE_ROLE:-single}" == "egress" ]]; then
  echo "Rendering egress Xray config..."
  render_xray_config_from_env
  systemctl restart xray
  echo "Egress upgrade complete."
  exit 0
fi

echo "Updating panel files..."
install -d -m 0755 /opt/proxy-panel
rm -rf /opt/proxy-panel/panel
cp -a "$ROOT_DIR/panel" /opt/proxy-panel/

if [[ ! -x /opt/proxy-panel/.venv/bin/python ]]; then
  python3 -m venv /opt/proxy-panel/.venv
fi

/opt/proxy-panel/.venv/bin/pip install --upgrade -r /opt/proxy-panel/panel/requirements.txt
sync_database_runtime_settings
/opt/proxy-panel/.venv/bin/python -m panel.cli render

render_template "$ROOT_DIR/templates/proxy-panel.service.tpl" /etc/systemd/system/proxy-panel.service
systemctl daemon-reload
render_upgrade_nginx_config

systemctl restart proxy-panel xray
echo "Upgrade complete."
