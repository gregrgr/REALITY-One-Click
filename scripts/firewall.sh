#!/usr/bin/env bash

configure_firewall() {
  if ! command_exists ufw; then
    warn "ufw is not installed; firewall step skipped."
    return
  fi

  run_cmd ufw allow "${SSH_PORT}/tcp"
  run_cmd ufw allow 80/tcp
  run_cmd ufw allow "${XRAY_PUBLIC_PORT}/tcp"
  run_cmd ufw allow "${PANEL_HTTPS_PORT}/tcp"
  run_cmd ufw --force enable
}
