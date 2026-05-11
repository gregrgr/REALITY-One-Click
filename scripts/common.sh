#!/usr/bin/env bash

# shellcheck disable=SC2034
PROJECT_NAME="proxy-panel"
ETC_DIR="/etc/proxy-panel"
ENV_FILE="$ETC_DIR/panel.env"
DATA_DIR="/var/lib/proxy-panel"
LOG_DIR="/var/log/proxy-panel"
OPT_DIR="/opt/proxy-panel"
ACME_WEBROOT="/var/www/acme"

ASSUME_YES="${ASSUME_YES:-0}"
DRY_RUN="${DRY_RUN:-0}"
ACME_STAGING="${ACME_STAGING:-0}"
SKIP_FIREWALL="${SKIP_FIREWALL:-0}"
NODE_ROLE="${NODE_ROLE:-single}"
EGRESS_BACKEND_PORT="${EGRESS_BACKEND_PORT:-10808}"
EGRESS_BACKEND_PROTOCOL="${EGRESS_BACKEND_PROTOCOL:-socks}"
TAILSCALE_REQUIRED="${TAILSCALE_REQUIRED:-yes}"
LATENCY_PROBE_URL="${LATENCY_PROBE_URL:-https://www.gstatic.com/generate_204}"
LATENCY_IP_CHECK_URL="${LATENCY_IP_CHECK_URL:-https://api.ipify.org}"
LATENCY_TIMEOUT_SECONDS="${LATENCY_TIMEOUT_SECONDS:-5}"
LATENCY_CACHE_SECONDS="${LATENCY_CACHE_SECONDS:-30}"

log() {
  printf '\033[1;32m[+] %s\033[0m\n' "$*"
}

warn() {
  printf '\033[1;33m[!] %s\033[0m\n' "$*" >&2
}

die() {
  printf '\033[1;31m[x] %s\033[0m\n' "$*" >&2
  exit 1
}

run_cmd() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %s\n' "$*"
    return 0
  fi
  "$@"
}

require_root() {
  if [[ "$DRY_RUN" == "1" ]]; then
    return 0
  fi
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "Please run this installer as root."
}

require_ubuntu_2204() {
  if [[ ! -r /etc/os-release ]]; then
    die "Cannot detect operating system."
  fi
  # shellcheck disable=SC1091
  source /etc/os-release
  if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "22.04" ]]; then
    die "This installer supports Ubuntu 22.04 only. Detected: ${PRETTY_NAME:-unknown}."
  fi
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

prompt_default() {
  local var_name="$1"
  local label="$2"
  local default_value="$3"
  local current_value="${!var_name:-}"

  if [[ -n "$current_value" ]]; then
    export "$var_name=$current_value"
    return
  fi

  if [[ "$ASSUME_YES" == "1" ]]; then
    export "$var_name=$default_value"
    return
  fi

  local input
  read -r -p "$label [$default_value]: " input
  export "$var_name=${input:-$default_value}"
}

prompt_required() {
  local var_name="$1"
  local label="$2"
  local current_value="${!var_name:-}"

  if [[ -n "$current_value" ]]; then
    export "$var_name=$current_value"
    return
  fi

  if [[ "$ASSUME_YES" == "1" ]]; then
    die "$var_name is required in --assume-yes mode."
  fi

  local input
  while [[ -z "$current_value" ]]; do
    read -r -p "$label: " input
    current_value="$input"
  done
  export "$var_name=$current_value"
}

prompt_secret_required() {
  local var_name="$1"
  local label="$2"
  local current_value="${!var_name:-}"

  if [[ -n "$current_value" ]]; then
    export "$var_name=$current_value"
    return
  fi

  if [[ "$ASSUME_YES" == "1" ]]; then
    die "$var_name is required in --assume-yes mode."
  fi

  local input
  while [[ -z "$current_value" ]]; do
    read -r -s -p "$label: " input
    printf '\n'
    current_value="$input"
  done
  export "$var_name=$current_value"
}

set_default() {
  local var_name="$1"
  local default_value="$2"
  local current_value="${!var_name:-}"

  export "$var_name=${current_value:-$default_value}"
}

generate_password() {
  openssl rand -base64 24 | tr -d '\n'
}

random_hex() {
  local bytes="$1"
  openssl rand -hex "$bytes" | tr -d '\n'
}

reality_server_from_dest() {
  local dest="$1"
  printf '%s' "${dest%%:*}"
}

detect_public_ipv4() {
  local endpoints=(
    "https://api.ipify.org"
    "https://ifconfig.me/ip"
    "https://icanhazip.com"
  )
  local endpoint ip

  if [[ "$DRY_RUN" == "1" ]] || ! command_exists curl; then
    return 1
  fi

  for endpoint in "${endpoints[@]}"; do
    ip="$(curl -4fsS --max-time 5 "$endpoint" 2>/dev/null | tr -d '[:space:]' || true)"
    if [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
      printf '%s\n' "$ip"
      return 0
    fi
  done

  return 1
}

get_tailscale_ip() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '%s\n' "${EGRESS_BACKEND_LISTEN:-100.64.0.1}"
    return 0
  fi

  command_exists ip || return 1
  ip -4 addr show tailscale0 2>/dev/null \
    | awk '/inet / { sub(/\/.*/, "", $2); print $2; exit }' \
    | grep -E '^100\.([0-9]{1,3}\.){2}[0-9]{1,3}$'
}

validate_node_role() {
  case "${NODE_ROLE:-single}" in
    single|relay|egress) ;;
    *) die "NODE_ROLE must be one of: single, relay, egress." ;;
  esac
}

is_tailscale_ipv4() {
  [[ "$1" =~ ^100\.([0-9]{1,3}\.){2}[0-9]{1,3}$ ]]
}

require_tailscale_ready() {
  if [[ "${NODE_ROLE:-single}" == "single" || "${TAILSCALE_REQUIRED:-yes}" != "yes" ]]; then
    return
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] tailscale status\n'
    return
  fi

  command_exists tailscale || die "Tailscale is required for NODE_ROLE=${NODE_ROLE}. Please install tailscale first."

  if tailscale status >/dev/null 2>&1; then
    return
  fi

  if [[ -n "${TAILSCALE_AUTHKEY:-}" ]]; then
    run_cmd tailscale up --authkey "$TAILSCALE_AUTHKEY"
    tailscale status >/dev/null 2>&1 || die "Tailscale is still not ready. Please run 'tailscale up' and retry."
    return
  fi

  die "Tailscale is not ready. Please run 'tailscale up' first."
}

validate_tailscale_bind_ip() {
  if [[ "${NODE_ROLE:-single}" != "egress" ]]; then
    return
  fi

  if [[ -z "${EGRESS_BACKEND_LISTEN:-}" ]]; then
    EGRESS_BACKEND_LISTEN="$(get_tailscale_ip || true)"
    export EGRESS_BACKEND_LISTEN
  fi

  [[ -n "${EGRESS_BACKEND_LISTEN:-}" ]] || die "EGRESS_BACKEND_LISTEN is required for egress mode and could not be detected from tailscale0."
  [[ "$EGRESS_BACKEND_LISTEN" != "0.0.0.0" ]] || die "EGRESS_BACKEND_LISTEN must not be 0.0.0.0."
  is_tailscale_ipv4 "$EGRESS_BACKEND_LISTEN" || die "EGRESS_BACKEND_LISTEN must be a Tailscale IPv4 address in 100.x.x.x."
}

require_relay_can_reach_egress() {
  if [[ "${NODE_ROLE:-single}" != "relay" ]]; then
    return
  fi

  [[ -n "${EGRESS_TAILSCALE_IP:-}" ]] || die "EGRESS_TAILSCALE_IP is required for relay mode."

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] ping -c 2 %s\n' "$EGRESS_TAILSCALE_IP"
    printf '[dry-run] nc -vz %s %s\n' "$EGRESS_TAILSCALE_IP" "$EGRESS_BACKEND_PORT"
    return
  fi

  if command_exists ping; then
    ping -c 2 "$EGRESS_TAILSCALE_IP" >/dev/null 2>&1 || warn "Cannot ping egress Tailscale IP: $EGRESS_TAILSCALE_IP"
  else
    warn "ping is not installed; skipped egress ICMP check."
  fi

  command_exists nc || die "nc is required to validate relay -> egress connectivity."
  nc -vz "$EGRESS_TAILSCALE_IP" "$EGRESS_BACKEND_PORT" >/dev/null 2>&1 \
    || die "Relay cannot connect to egress backend ${EGRESS_TAILSCALE_IP}:${EGRESS_BACKEND_PORT}."
}

collect_install_config() {
  local migrate_split_arch=0
  if [[ -r "$ENV_FILE" ]] && ! grep -q '^PANEL_HTTPS_PORT=' "$ENV_FILE"; then
    migrate_split_arch=1
  fi

  if [[ -r "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
  fi

  set_default NODE_ROLE "${NODE_ROLE:-single}"
  validate_node_role
  set_default EGRESS_BACKEND_PORT "${EGRESS_BACKEND_PORT:-10808}"
  set_default EGRESS_BACKEND_PROTOCOL "${EGRESS_BACKEND_PROTOCOL:-socks}"
  set_default TAILSCALE_REQUIRED "${TAILSCALE_REQUIRED:-yes}"
  set_default LATENCY_PROBE_URL "${LATENCY_PROBE_URL:-https://www.gstatic.com/generate_204}"
  set_default LATENCY_IP_CHECK_URL "${LATENCY_IP_CHECK_URL:-https://api.ipify.org}"
  set_default LATENCY_TIMEOUT_SECONDS "${LATENCY_TIMEOUT_SECONDS:-5}"
  set_default LATENCY_CACHE_SECONDS "${LATENCY_CACHE_SECONDS:-30}"

  if [[ "$NODE_ROLE" != "egress" ]]; then
    prompt_required PANEL_DOMAIN "Panel domain, for example panel.example.com"
    prompt_required ACME_EMAIL "Let's Encrypt email"
    prompt_default ADMIN_USER "Admin username" "${ADMIN_USER:-admin}"
  fi

  if [[ "$NODE_ROLE" != "egress" && -z "${ADMIN_PASSWORD:-}" ]]; then
    if [[ "$ASSUME_YES" == "1" ]]; then
      ADMIN_PASSWORD="$(generate_password)"
    else
      local password_input
      read -r -s -p "Admin password [auto-generate]: " password_input
      printf '\n'
      ADMIN_PASSWORD="${password_input:-$(generate_password)}"
    fi
    export ADMIN_PASSWORD
  fi

  set_default NODE_NAME "vps-reality-01"
  if [[ "$NODE_ROLE" != "egress" && -z "${PUBLIC_HOST:-}" ]]; then
    PUBLIC_HOST="$(detect_public_ipv4 || true)"
    if [[ -z "$PUBLIC_HOST" ]]; then
      warn "Could not detect public IPv4; falling back PUBLIC_HOST to PANEL_DOMAIN."
      PUBLIC_HOST="$PANEL_DOMAIN"
    fi
    export PUBLIC_HOST
  fi
  if [[ "$migrate_split_arch" == "1" && "${XRAY_LISTEN:-}" == "127.0.0.1" && "${XRAY_PORT:-}" == "1443" ]]; then
    XRAY_LISTEN="0.0.0.0"
    XRAY_PORT="443"
    XRAY_PUBLIC_PORT="443"
    export XRAY_LISTEN XRAY_PORT XRAY_PUBLIC_PORT
  fi
  set_default XRAY_PUBLIC_PORT "443"
  set_default XRAY_LISTEN "0.0.0.0"
  set_default XRAY_PORT "443"
  set_default PANEL_HTTPS_PORT "8443"
  set_default REALITY_DEST "www.microsoft.com:443"
  set_default REALITY_SERVERNAME "$(reality_server_from_dest "$REALITY_DEST")"
  set_default REALITY_FINGERPRINT "chrome"
  set_default XRAY_API_HOST "127.0.0.1"
  set_default XRAY_API_PORT "10085"
  prompt_default SSH_PORT "SSH port to allow in firewall/security group" "${SSH_PORT:-22}"
  if [[ "$NODE_ROLE" == "relay" ]]; then
    prompt_required EGRESS_TAILSCALE_IP "Egress Tailscale IP, for example 100.x.x.x"
  fi
  if [[ "$NODE_ROLE" != "egress" ]]; then
    prompt_default ACME_CHALLENGE "Certificate challenge method, http or cloudflare" "${ACME_CHALLENGE:-http}"
  else
    set_default ACME_CHALLENGE "http"
  fi

  if [[ "$NODE_ROLE" != "egress" && "$ACME_CHALLENGE" == "cloudflare" ]]; then
    prompt_secret_required CLOUDFLARE_API_TOKEN "Cloudflare DNS API token"
    set_default CLOUDFLARE_PROPAGATION_SECONDS "60"
  fi

  set_default ENABLE_UFW "yes"

  REALITY_SPIDER_X="${REALITY_SPIDER_X:-/}"
  export NODE_ROLE EGRESS_TAILSCALE_IP EGRESS_BACKEND_PORT EGRESS_BACKEND_LISTEN
  export EGRESS_BACKEND_PROTOCOL TAILSCALE_REQUIRED REALITY_SPIDER_X
  export LATENCY_PROBE_URL LATENCY_IP_CHECK_URL LATENCY_TIMEOUT_SECONDS LATENCY_CACHE_SECONDS
  export XRAY_API_HOST XRAY_API_PORT ACME_CHALLENGE CLOUDFLARE_PROPAGATION_SECONDS
}

validate_domain() {
  local domain="$1"
  [[ "$domain" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$ ]]
}

validate_install_config() {
  validate_node_role
  if [[ "$NODE_ROLE" != "egress" ]]; then
    validate_domain "$PANEL_DOMAIN" || die "Invalid PANEL_DOMAIN: $PANEL_DOMAIN"
    validate_domain "$REALITY_SERVERNAME" || die "Invalid REALITY_SERVERNAME: $REALITY_SERVERNAME"
    if [[ "${REALITY_SERVERNAME,,}" == "${PANEL_DOMAIN,,}" ]]; then
      die "REALITY_SERVERNAME must not equal PANEL_DOMAIN. Use a camouflage SNI such as www.microsoft.com, otherwise Nginx SNI routing sends REALITY clients to the panel HTTPS backend."
    fi
  fi
  [[ "$XRAY_PUBLIC_PORT" =~ ^[0-9]+$ ]] || die "Invalid XRAY_PUBLIC_PORT: $XRAY_PUBLIC_PORT"
  [[ "$XRAY_PORT" =~ ^[0-9]+$ ]] || die "Invalid XRAY_PORT: $XRAY_PORT"
  [[ "$PANEL_HTTPS_PORT" =~ ^[0-9]+$ ]] || die "Invalid PANEL_HTTPS_PORT: $PANEL_HTTPS_PORT"
  [[ "$XRAY_API_PORT" =~ ^[0-9]+$ ]] || die "Invalid XRAY_API_PORT: $XRAY_API_PORT"
  [[ "$EGRESS_BACKEND_PORT" =~ ^[0-9]+$ ]] || die "Invalid EGRESS_BACKEND_PORT: $EGRESS_BACKEND_PORT"
  if (( 10#$EGRESS_BACKEND_PORT < 1 || 10#$EGRESS_BACKEND_PORT > 65535 )); then
    die "Invalid EGRESS_BACKEND_PORT: $EGRESS_BACKEND_PORT"
  fi
  [[ "$EGRESS_BACKEND_PROTOCOL" == "socks" ]] || die "Only EGRESS_BACKEND_PROTOCOL=socks is currently supported."
  if [[ "$NODE_ROLE" == "relay" ]]; then
    [[ -n "${EGRESS_TAILSCALE_IP:-}" ]] || die "EGRESS_TAILSCALE_IP is required for relay mode."
    is_tailscale_ipv4 "$EGRESS_TAILSCALE_IP" || die "EGRESS_TAILSCALE_IP must be a Tailscale IPv4 address in 100.x.x.x."
  fi
  validate_tailscale_bind_ip
  [[ "$SSH_PORT" =~ ^[0-9]+$ ]] || die "Invalid SSH_PORT: $SSH_PORT"
  if (( 10#$SSH_PORT < 1 || 10#$SSH_PORT > 65535 )); then
    die "Invalid SSH_PORT: $SSH_PORT"
  fi
  if [[ "$NODE_ROLE" != "egress" ]]; then
    if [[ "$PANEL_HTTPS_PORT" == "$XRAY_PUBLIC_PORT" || "$PANEL_HTTPS_PORT" == "$XRAY_PORT" ]]; then
      die "PANEL_HTTPS_PORT must be different from Xray port 443."
    fi
  fi
  [[ "$ACME_CHALLENGE" == "http" || "$ACME_CHALLENGE" == "cloudflare" ]] || die "ACME_CHALLENGE must be http or cloudflare."
  if [[ "$ACME_CHALLENGE" == "cloudflare" && -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
    die "CLOUDFLARE_API_TOKEN is required when ACME_CHALLENGE=cloudflare."
  fi

  if [[ "$NODE_ROLE" != "egress" ]]; then
    if command_exists getent; then
      getent ahosts "$PANEL_DOMAIN" >/dev/null || warn "Domain does not resolve from this machine yet: $PANEL_DOMAIN"
    fi
  fi
}

install_base_packages() {
  run_cmd apt-get update
  local packages=(
    ca-certificates curl wget unzip jq openssl uuid-runtime \
    python3 python3-venv python3-pip gettext-base sqlite3 ufw \
    iproute2 iputils-ping netcat-openbsd
  )

  if [[ "${NODE_ROLE:-single}" != "egress" ]]; then
    packages+=(nginx certbot python3-certbot-nginx)
    if [[ "${ACME_CHALLENGE:-http}" == "cloudflare" ]]; then
      packages+=(python3-certbot-dns-cloudflare)
    fi
  fi

  run_cmd apt-get install -y "${packages[@]}"
}

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[&|]/\\&/g'
}

render_template() {
  local src="$1"
  local dest="$2"
  local tmp
  tmp="$(mktemp)"
  cp "$src" "$tmp"

  local vars=(
    PANEL_DOMAIN ACME_WEBROOT XRAY_LISTEN XRAY_PORT XRAY_PUBLIC_PORT
    PANEL_HTTPS_PORT
    REALITY_DEST REALITY_SERVERNAME REALITY_PRIVATE_KEY REALITY_PUBLIC_KEY
    REALITY_SHORT_ID REALITY_SPIDER_X REALITY_FINGERPRINT
    XRAY_API_HOST XRAY_API_PORT ACME_CHALLENGE CLOUDFLARE_PROPAGATION_SECONDS
    NODE_NAME PUBLIC_HOST SSH_PORT DATA_DIR LOG_DIR OPT_DIR ENV_FILE
    NODE_ROLE EGRESS_TAILSCALE_IP EGRESS_BACKEND_PORT EGRESS_BACKEND_LISTEN
    EGRESS_BACKEND_PROTOCOL TAILSCALE_REQUIRED
    LATENCY_PROBE_URL LATENCY_IP_CHECK_URL LATENCY_TIMEOUT_SECONDS LATENCY_CACHE_SECONDS
  )

  local var value escaped
  for var in "${vars[@]}"; do
    value="${!var:-}"
    escaped="$(escape_sed_replacement "$value")"
    sed -i "s|__${var}__|$escaped|g" "$tmp"
  done

  run_cmd install -D -m 0644 "$tmp" "$dest"
  rm -f "$tmp"
}

write_env_file() {
  run_cmd install -d -m 0750 "$ETC_DIR"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] write %s\n' "$ENV_FILE"
    return
  fi

  local public_base="${PROXY_PANEL_PUBLIC_BASE:-https://${PANEL_DOMAIN:-localhost}:${PANEL_HTTPS_PORT:-8443}}"
  cat > "$ENV_FILE" <<EOF
PROXY_PANEL_DB=$DATA_DIR/panel.db
PROXY_PANEL_CONFIG=/usr/local/etc/xray/config.json
PROXY_PANEL_SECRET_KEY=${PROXY_PANEL_SECRET_KEY:-}
PROXY_PANEL_PUBLIC_BASE=${public_base}
NODE_ROLE=${NODE_ROLE}
PANEL_DOMAIN=${PANEL_DOMAIN:-}
PANEL_HTTPS_PORT=${PANEL_HTTPS_PORT:-8443}
ACME_EMAIL=${ACME_EMAIL:-}
NODE_NAME=${NODE_NAME}
PUBLIC_HOST=${PUBLIC_HOST:-}
SSH_PORT=${SSH_PORT}
XRAY_PUBLIC_PORT=${XRAY_PUBLIC_PORT}
XRAY_LISTEN=${XRAY_LISTEN}
XRAY_PORT=${XRAY_PORT}
REALITY_DEST=${REALITY_DEST:-}
REALITY_SERVERNAME=${REALITY_SERVERNAME:-}
REALITY_PRIVATE_KEY=${REALITY_PRIVATE_KEY:-}
REALITY_PUBLIC_KEY=${REALITY_PUBLIC_KEY:-}
REALITY_SHORT_ID=${REALITY_SHORT_ID:-}
REALITY_SPIDER_X=${REALITY_SPIDER_X:-/}
REALITY_FINGERPRINT=${REALITY_FINGERPRINT:-chrome}
XRAY_API_HOST=${XRAY_API_HOST}
XRAY_API_PORT=${XRAY_API_PORT}
ACME_CHALLENGE=${ACME_CHALLENGE}
CLOUDFLARE_PROPAGATION_SECONDS=${CLOUDFLARE_PROPAGATION_SECONDS:-60}
EGRESS_TAILSCALE_IP=${EGRESS_TAILSCALE_IP:-}
EGRESS_BACKEND_PORT=${EGRESS_BACKEND_PORT}
EGRESS_BACKEND_LISTEN=${EGRESS_BACKEND_LISTEN:-}
EGRESS_BACKEND_PROTOCOL=${EGRESS_BACKEND_PROTOCOL}
TAILSCALE_REQUIRED=${TAILSCALE_REQUIRED}
LATENCY_PROBE_URL=${LATENCY_PROBE_URL}
LATENCY_IP_CHECK_URL=${LATENCY_IP_CHECK_URL}
LATENCY_TIMEOUT_SECONDS=${LATENCY_TIMEOUT_SECONDS}
LATENCY_CACHE_SECONDS=${LATENCY_CACHE_SECONDS}
EOF
  chmod 0640 "$ENV_FILE"
}

systemctl_if_available() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] systemctl %s\n' "$*"
    return
  fi
  if command_exists systemctl; then
    run_cmd systemctl "$@"
  else
    warn "systemctl not available; skipped: systemctl $*"
  fi
}

print_install_summary() {
  cat <<EOF

Installation complete.

Panel:        https://${PANEL_DOMAIN}:${PANEL_HTTPS_PORT}
Admin user:   ${ADMIN_USER}
Admin pass:   ${ADMIN_PASSWORD}
Clash sub:    https://${PANEL_DOMAIN}:${PANEL_HTTPS_PORT}/sub/<user-token>/clash.yaml
VLESS sub:    https://${PANEL_DOMAIN}:${PANEL_HTTPS_PORT}/sub/<user-token>/vless.txt

Open these inbound ports in your VPS cloud security group:
  SSH:             ${SSH_PORT}/tcp
  HTTP / ACME:     80/tcp
  Xray REALITY:    ${XRAY_PUBLIC_PORT}/tcp
  Panel / Sub:     ${PANEL_HTTPS_PORT}/tcp

Useful commands:
  proxy-panel status
  proxy-panel latency
  proxy-panel list-users
  proxy-panel add-user alice
  proxy-panel show-sub alice
  proxy-panel restart
EOF
}

print_egress_summary() {
  cat <<EOF

Egress installation complete.

Role:          egress
Backend:       ${EGRESS_BACKEND_LISTEN}:${EGRESS_BACKEND_PORT} (${EGRESS_BACKEND_PROTOCOL})
Xray config:   /usr/local/etc/xray/config.json

Open these inbound ports in your VPS cloud security group:
  SSH:             ${SSH_PORT}/tcp

Do not open ${EGRESS_BACKEND_PORT}/tcp to the public Internet. It should be reachable only through tailscale0.

Useful commands:
  systemctl status xray --no-pager
  ss -lntp | grep ${EGRESS_BACKEND_PORT}
  bash scripts/validate_two_vps.sh egress
EOF
}
