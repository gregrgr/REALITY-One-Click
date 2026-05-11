#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=scripts/common.sh
source "$ROOT_DIR/scripts/common.sh"
# shellcheck source=scripts/install_xray.sh
source "$ROOT_DIR/scripts/install_xray.sh"
# shellcheck source=scripts/install_nginx.sh
source "$ROOT_DIR/scripts/install_nginx.sh"
# shellcheck source=scripts/install_cert.sh
source "$ROOT_DIR/scripts/install_cert.sh"
# shellcheck source=scripts/install_panel.sh
source "$ROOT_DIR/scripts/install_panel.sh"
# shellcheck source=scripts/firewall.sh
source "$ROOT_DIR/scripts/firewall.sh"

usage() {
  cat <<'USAGE'
Usage: bash install.sh [options]

Options:
  --assume-yes       Use environment variables and defaults without prompts.
  --dry-run          Print the main actions without changing the system.
  --staging          Use Let's Encrypt staging certificates.
  --skip-firewall    Do not configure UFW.
  -h, --help         Show this help.

Environment variables for non-interactive installs:
  NODE_ROLE          single, relay, or egress. Default: single
  PANEL_DOMAIN       Required. HTTPS panel and subscription domain.
  ACME_EMAIL         Required. Let's Encrypt account email.
  ADMIN_USER         Default: admin
  ADMIN_PASSWORD     Default: generated strong password
  NODE_NAME          Optional override. Default: vps-reality-01
  PUBLIC_HOST        Optional override. Default: auto-detected public IPv4.
  XRAY_PUBLIC_PORT   Optional override. Default: 443
  XRAY_LISTEN        Optional override. Default: 0.0.0.0
  XRAY_PORT          Optional override. Default: 443
  PANEL_HTTPS_PORT   Optional override. Default: 8443
  REALITY_DEST       Optional override. Default: www.microsoft.com:443
  REALITY_SERVERNAME Optional override. Default: REALITY_DEST host
  XRAY_API_HOST      Optional override. Default: 127.0.0.1
  XRAY_API_PORT      Optional override. Default: 10085
  SSH_PORT           SSH port to allow in UFW/security group. Default: 22
  EGRESS_TAILSCALE_IP
                     Required when NODE_ROLE=relay.
  EGRESS_BACKEND_PORT
                     Egress backend port. Default: 10808
  EGRESS_BACKEND_LISTEN
                     Egress Tailscale listen IP. Auto-detected on egress.
  EGRESS_BACKEND_PROTOCOL
                     Default: socks
  TAILSCALE_REQUIRED Default: yes for relay/egress checks.
  ACME_CHALLENGE     Default: http. Use cloudflare for DNS API.
  CLOUDFLARE_API_TOKEN
                     Required when ACME_CHALLENGE=cloudflare.
  CLOUDFLARE_PROPAGATION_SECONDS
                     Default: 60
  ENABLE_UFW         Default: yes
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --assume-yes)
      ASSUME_YES=1
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    --staging)
      ACME_STAGING=1
      ;;
    --skip-firewall)
      SKIP_FIREWALL=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
  shift
done

main() {
  require_root
  require_ubuntu_2204
  collect_install_config

  log "Installing base packages"
  install_base_packages

  if [[ "$NODE_ROLE" != "single" ]]; then
    require_tailscale_ready
  fi
  validate_install_config
  if [[ "$NODE_ROLE" == "relay" ]]; then
    require_relay_can_reach_egress
  fi

  log "Installing Xray Core"
  install_xray_core

  if [[ "$NODE_ROLE" == "egress" ]]; then
    log "Rendering egress Xray backend config"
    write_env_file
    render_xray_config_from_env
    systemctl_if_available enable xray
    systemctl_if_available restart xray

    if [[ "${SKIP_FIREWALL:-0}" != "1" && "${ENABLE_UFW:-yes}" == "yes" ]]; then
      configure_firewall
    fi

    print_egress_summary
    return
  fi

  ensure_reality_material

  log "Preparing Nginx HTTP site"
  install_nginx_base
  render_nginx_http_config
  reload_or_start_nginx

  log "Requesting HTTPS certificate"
  install_certificate

  log "Rendering Nginx panel HTTPS config"
  render_nginx_tls_config
  disable_nginx_stream_config
  reload_or_start_nginx

  log "Installing management backend"
  install_panel_backend
  initialize_panel_data
  render_panel_xray_config
  restart_panel_services

  if [[ "${SKIP_FIREWALL:-0}" != "1" && "${ENABLE_UFW:-yes}" == "yes" ]]; then
    configure_firewall
  fi

  print_install_summary
}

main "$@"
