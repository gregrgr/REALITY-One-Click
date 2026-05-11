#!/usr/bin/env bash

configure_firewall_single() {
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

configure_firewall_relay() {
  configure_firewall_single
}

ensure_egress_backend_not_public() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] check egress backend is not listening on 0.0.0.0:%s\n' "$EGRESS_BACKEND_PORT"
    return
  fi

  if ss -lnt 2>/dev/null | grep -Eq "(^|[[:space:]])(0\.0\.0\.0|\*):${EGRESS_BACKEND_PORT}[[:space:]]"; then
    die "Egress backend must not listen on 0.0.0.0:${EGRESS_BACKEND_PORT}."
  fi
}

configure_firewall_egress() {
  if ! command_exists ufw; then
    warn "ufw is not installed; firewall step skipped."
    return
  fi

  ensure_egress_backend_not_public
  run_cmd ufw allow "${SSH_PORT}/tcp"
  run_cmd ufw allow in on tailscale0 to any port "${EGRESS_BACKEND_PORT}" proto tcp
  run_cmd ufw deny in to any port "${EGRESS_BACKEND_PORT}" proto tcp
  run_cmd ufw --force enable
}

configure_firewall() {
  case "${NODE_ROLE:-single}" in
    single) configure_firewall_single ;;
    relay) configure_firewall_relay ;;
    egress) configure_firewall_egress ;;
    *) die "Unknown NODE_ROLE for firewall: ${NODE_ROLE:-}" ;;
  esac
}
