#!/usr/bin/env bash

install_xray_core() {
  if command_exists xray || [[ -x /usr/local/bin/xray ]]; then
    log "Xray is already installed"
    return
  fi

  local tmp_dir
  tmp_dir="$(mktemp -d)"

  run_cmd curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh -o "$tmp_dir/install-release.sh"
  run_cmd bash "$tmp_dir/install-release.sh" install
  rm -rf "$tmp_dir"
}

xray_bin() {
  if command_exists xray; then
    command -v xray
  elif [[ -x /usr/local/bin/xray ]]; then
    printf '%s\n' /usr/local/bin/xray
  else
    die "xray binary not found."
  fi
}

extract_x25519_key() {
  local key_name="$1"
  awk -v key_name="$key_name" '
    {
      line = $0
      gsub(/\r/, "", line)
      normalized = tolower(line)
      gsub(/[[:space:]_-]/, "", normalized)
      if (normalized ~ key_name) {
        value = line
        if (value ~ /[:：=]/) {
          sub(/^[^:：=]*[:：=][[:space:]]*/, "", value)
        } else {
          sub(/^[^[:space:]]+[[:space:]]+/, "", value)
        }
        sub(/^[[:space:]]+/, "", value)
        sub(/[[:space:]]+$/, "", value)
        print value
        exit
      }
    }
  '
}

ensure_reality_material() {
  if [[ "$DRY_RUN" == "1" ]]; then
    REALITY_PRIVATE_KEY="${REALITY_PRIVATE_KEY:-dry_run_private_key}"
    REALITY_PUBLIC_KEY="${REALITY_PUBLIC_KEY:-dry_run_public_key}"
    REALITY_SHORT_ID="${REALITY_SHORT_ID:-0123456789abcdef}"
    PROXY_PANEL_SECRET_KEY="${PROXY_PANEL_SECRET_KEY:-dry_run_secret_key}"
    export REALITY_PRIVATE_KEY REALITY_PUBLIC_KEY REALITY_SHORT_ID PROXY_PANEL_SECRET_KEY
    return
  fi

  if [[ -n "${REALITY_PRIVATE_KEY:-}" && -n "${REALITY_PUBLIC_KEY:-}" && -n "${REALITY_SHORT_ID:-}" ]]; then
    return
  fi

  local bin key_output
  bin="$(xray_bin)"
  if ! key_output="$("$bin" x25519 2>&1)"; then
    die "Failed to run '$bin x25519'. Output: $key_output"
  fi

  REALITY_PRIVATE_KEY="${REALITY_PRIVATE_KEY:-$(printf '%s\n' "$key_output" | extract_x25519_key "privatekey")}"
  REALITY_PUBLIC_KEY="${REALITY_PUBLIC_KEY:-$(printf '%s\n' "$key_output" | extract_x25519_key "publickey")}"
  REALITY_SHORT_ID="${REALITY_SHORT_ID:-$(random_hex 8)}"
  PROXY_PANEL_SECRET_KEY="${PROXY_PANEL_SECRET_KEY:-$(random_hex 32)}"

  if [[ -z "$REALITY_PRIVATE_KEY" || -z "$REALITY_PUBLIC_KEY" ]]; then
    die "Failed to parse REALITY key pair from '$bin x25519'. Output: $key_output"
  fi

  export REALITY_PRIVATE_KEY REALITY_PUBLIC_KEY REALITY_SHORT_ID PROXY_PANEL_SECRET_KEY
}

render_xray_config_from_env() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] render xray config from environment\n'
    return
  fi

  PYTHONPATH="$ROOT_DIR" python3 - <<'PY'
import os

from panel.xray_config import write_xray_config


ENV_TO_SETTING = {
    "NODE_ROLE": "node_role",
    "XRAY_LISTEN": "xray_listen",
    "XRAY_PORT": "xray_port",
    "XRAY_API_HOST": "xray_api_host",
    "XRAY_API_PORT": "xray_api_port",
    "REALITY_DEST": "reality_dest",
    "REALITY_SERVERNAME": "reality_server_name",
    "REALITY_PRIVATE_KEY": "reality_private_key",
    "REALITY_PUBLIC_KEY": "reality_public_key",
    "REALITY_SHORT_ID": "reality_short_id",
    "REALITY_SPIDER_X": "reality_spider_x",
    "REALITY_FINGERPRINT": "reality_fingerprint",
    "EGRESS_TAILSCALE_IP": "egress_tailscale_ip",
    "EGRESS_BACKEND_PORT": "egress_backend_port",
    "EGRESS_BACKEND_LISTEN": "egress_backend_listen",
    "EGRESS_BACKEND_PROTOCOL": "egress_backend_protocol",
}

settings = {
    setting: value
    for env_name, setting in ENV_TO_SETTING.items()
    if (value := os.environ.get(env_name))
}
write_xray_config(
    os.environ.get("PROXY_PANEL_CONFIG", "/usr/local/etc/xray/config.json"),
    settings,
    [],
)
PY
}
