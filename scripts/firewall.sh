#!/usr/bin/env bash

configure_firewall() {
  if ! command_exists ufw; then
    warn "ufw is not installed; firewall step skipped."
    return
  fi

  run_cmd ufw allow OpenSSH
  run_cmd ufw allow 80/tcp
  run_cmd ufw allow 443/tcp
  run_cmd ufw --force enable
}
