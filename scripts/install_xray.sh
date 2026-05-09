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
  key_output="$("$bin" x25519)"

  REALITY_PRIVATE_KEY="${REALITY_PRIVATE_KEY:-$(printf '%s\n' "$key_output" | awk -F': ' '/Private key/ {print $2}')}"
  REALITY_PUBLIC_KEY="${REALITY_PUBLIC_KEY:-$(printf '%s\n' "$key_output" | awk -F': ' '/Public key/ {print $2}')}"
  REALITY_SHORT_ID="${REALITY_SHORT_ID:-$(random_hex 8)}"
  PROXY_PANEL_SECRET_KEY="${PROXY_PANEL_SECRET_KEY:-$(random_hex 32)}"

  [[ -n "$REALITY_PRIVATE_KEY" ]] || die "Failed to generate REALITY private key."
  [[ -n "$REALITY_PUBLIC_KEY" ]] || die "Failed to generate REALITY public key."

  export REALITY_PRIVATE_KEY REALITY_PUBLIC_KEY REALITY_SHORT_ID PROXY_PANEL_SECRET_KEY
}
