#!/usr/bin/env bash

install_panel_backend() {
  run_cmd install -d -m 0755 "$OPT_DIR"
  run_cmd install -d -m 0750 "$DATA_DIR"
  run_cmd install -d -m 0750 "$LOG_DIR"
  run_cmd install -d -m 0750 "$ETC_DIR"

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] copy panel package and create virtualenv\n'
  else
    rm -rf "$OPT_DIR/panel"
    cp -a "$ROOT_DIR/panel" "$OPT_DIR/"
    python3 -m venv "$OPT_DIR/.venv"
    "$OPT_DIR/.venv/bin/pip" install --upgrade pip wheel
    "$OPT_DIR/.venv/bin/pip" install -r "$OPT_DIR/panel/requirements.txt"
  fi

  write_env_file
  render_template "$ROOT_DIR/templates/proxy-panel.service.tpl" /etc/systemd/system/proxy-panel.service

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] install /usr/local/bin/proxy-panel wrapper\n'
  else
    cat > /usr/local/bin/proxy-panel <<EOF
#!/usr/bin/env bash
set -a
source "$ENV_FILE"
set +a
cd "$OPT_DIR"
exec "$OPT_DIR/.venv/bin/python" -m panel.cli "\$@"
EOF
    chmod 0755 /usr/local/bin/proxy-panel
  fi
}

initialize_panel_data() {
  local settings=(
    "node_role=${NODE_ROLE}"
    "panel_domain=${PANEL_DOMAIN}"
    "panel_https_port=${PANEL_HTTPS_PORT}"
    "node_name=${NODE_NAME}"
    "public_host=${PUBLIC_HOST}"
    "public_port=${XRAY_PUBLIC_PORT}"
    "xray_listen=${XRAY_LISTEN}"
    "xray_port=${XRAY_PORT}"
    "xray_api_host=${XRAY_API_HOST}"
    "xray_api_port=${XRAY_API_PORT}"
    "reality_dest=${REALITY_DEST}"
    "reality_server_name=${REALITY_SERVERNAME}"
    "reality_private_key=${REALITY_PRIVATE_KEY}"
    "reality_public_key=${REALITY_PUBLIC_KEY}"
    "reality_short_id=${REALITY_SHORT_ID}"
    "reality_spider_x=${REALITY_SPIDER_X}"
    "reality_fingerprint=${REALITY_FINGERPRINT}"
    "egress_tailscale_ip=${EGRESS_TAILSCALE_IP:-}"
    "egress_backend_port=${EGRESS_BACKEND_PORT}"
    "egress_backend_protocol=${EGRESS_BACKEND_PROTOCOL}"
  )

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] initialize panel database\n'
    return
  fi

  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a

  local setting_args=()
  local item
  for item in "${settings[@]}"; do
    setting_args+=(--setting "$item")
  done

  "$OPT_DIR/.venv/bin/python" -m panel.cli init \
    --admin-user "$ADMIN_USER" \
    --admin-password "$ADMIN_PASSWORD" \
    "${setting_args[@]}"

  "$OPT_DIR/.venv/bin/python" -m panel.cli ensure-user "$NODE_NAME"
}

render_panel_xray_config() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] render xray config\n'
    return
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  "$OPT_DIR/.venv/bin/python" -m panel.cli render
}

restart_panel_services() {
  systemctl_if_available daemon-reload
  systemctl_if_available enable proxy-panel
  systemctl_if_available restart proxy-panel
  systemctl_if_available enable xray
  systemctl_if_available restart xray
}
