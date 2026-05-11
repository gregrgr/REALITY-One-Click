#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=scripts/common.sh
source "$ROOT_DIR/scripts/common.sh"

if [[ -r "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

ROLE="${1:-${NODE_ROLE:-}}"
CONFIG_PATH="${PROXY_PANEL_CONFIG:-/usr/local/etc/xray/config.json}"
FAILURES=0

pass() {
  printf '[PASS] %s\n' "$*"
}

warn_check() {
  printf '[WARN] %s\n' "$*" >&2
}

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  FAILURES=$((FAILURES + 1))
}

require_role() {
  case "$ROLE" in
    relay|egress) ;;
    *) fail "Usage: bash scripts/validate_two_vps.sh relay|egress"; exit 1 ;;
  esac
}

check_tailscale_status() {
  if command_exists tailscale && tailscale status >/dev/null 2>&1; then
    pass "tailscale status is available"
  else
    fail "tailscale status failed; install tailscale and run 'tailscale up'"
  fi
}

check_no_exit_node() {
  if ! command_exists tailscale; then
    fail "tailscale command is missing"
    return
  fi
  if tailscale debug prefs --json >/tmp/proxy-panel-ts-prefs.json 2>/dev/null; then
    if jq -e '(.ExitNodeID == null or .ExitNodeID == "") and (.ExitNodeIP == null or .ExitNodeIP == "")' /tmp/proxy-panel-ts-prefs.json >/dev/null; then
      pass "tailscale exit node is not enabled"
    else
      fail "tailscale exit node appears to be enabled"
    fi
    rm -f /tmp/proxy-panel-ts-prefs.json
  else
    warn_check "could not inspect tailscale debug prefs; verify no exit node is enabled"
  fi
}

check_config_jq() {
  local filter="$1"
  local label="$2"
  if jq -e "$filter" "$CONFIG_PATH" >/dev/null; then
    pass "$label"
  else
    fail "$label"
  fi
}

validate_relay() {
  check_tailscale_status

  if [[ -n "${EGRESS_TAILSCALE_IP:-}" ]]; then
    pass "EGRESS_TAILSCALE_IP is set: $EGRESS_TAILSCALE_IP"
  else
    fail "EGRESS_TAILSCALE_IP is required"
  fi

  if [[ -n "${EGRESS_TAILSCALE_IP:-}" ]]; then
    if ping -c 2 "$EGRESS_TAILSCALE_IP" >/dev/null 2>&1; then
      pass "egress ping succeeded"
    else
      warn_check "egress ping failed; ICMP may be blocked"
    fi

    if nc -vz "$EGRESS_TAILSCALE_IP" "${EGRESS_BACKEND_PORT:-10808}" >/dev/null 2>&1; then
      pass "relay can connect to egress backend"
    else
      fail "relay cannot connect to ${EGRESS_TAILSCALE_IP}:${EGRESS_BACKEND_PORT:-10808}"
    fi
  fi

  if systemctl is-active --quiet xray; then
    pass "xray is active"
  else
    fail "xray is not active"
  fi

  check_config_jq '.outbounds[] | select(.tag == "egress-via-tailscale" and .protocol == "socks")' \
    "xray has egress-via-tailscale socks outbound"
  check_config_jq '.routing.rules[] | select((.inboundTag // []) | index("vless-reality")) | select(.outboundTag == "egress-via-tailscale")' \
    "vless-reality routes to egress-via-tailscale"
  check_no_exit_node
}

validate_egress() {
  if ip link show tailscale0 >/dev/null 2>&1; then
    pass "tailscale0 interface exists"
  else
    fail "tailscale0 interface is missing"
  fi

  local ts_ip
  ts_ip="$(get_tailscale_ip || true)"
  if [[ -n "$ts_ip" ]]; then
    pass "tailscale IPv4 detected: $ts_ip"
  else
    fail "could not detect tailscale IPv4"
  fi

  local port="${EGRESS_BACKEND_PORT:-10808}"
  local listeners
  listeners="$(ss -lntp 2>/dev/null | grep -E ":${port}[[:space:]]" || true)"
  if [[ -z "$listeners" ]]; then
    fail "port $port is not listening"
  elif printf '%s\n' "$listeners" | grep -Eq "(0\.0\.0\.0|\*):${port}[[:space:]]|^\S+[[:space:]]+\S+[[:space:]]+\S+[[:space:]]+\[::\]:${port}[[:space:]]"; then
    fail "egress backend is listening publicly: $listeners"
  elif [[ -n "${EGRESS_BACKEND_LISTEN:-}" ]] && printf '%s\n' "$listeners" | grep -F "${EGRESS_BACKEND_LISTEN}:${port}" >/dev/null; then
    pass "egress backend listens on ${EGRESS_BACKEND_LISTEN}:${port}"
  elif [[ -n "$ts_ip" ]] && printf '%s\n' "$listeners" | grep -F "${ts_ip}:${port}" >/dev/null; then
    pass "egress backend listens on ${ts_ip}:${port}"
  else
    fail "egress backend is not bound to tailscale IP: $listeners"
  fi

  if ufw status verbose 2>/dev/null | grep -E "tailscale0.*${port}|${port}.*tailscale0" >/dev/null; then
    pass "ufw allows backend on tailscale0"
  else
    fail "ufw does not show an allow rule for backend on tailscale0"
  fi

  if ufw status verbose 2>/dev/null | grep -E "^${port}/tcp[[:space:]]+ALLOW" | grep -v tailscale0 >/dev/null; then
    fail "ufw appears to allow backend port publicly"
  else
    pass "ufw does not show a public allow for backend port"
  fi

  if jq -e '.inbounds[]? | select(.tag == "vless-reality")' "$CONFIG_PATH" >/dev/null; then
    fail "xray config contains vless-reality inbound"
  else
    pass "xray config contains no vless-reality inbound"
  fi
  check_config_jq '.inbounds[] | select(.tag == "egress-socks-in" and .protocol == "socks")' \
    "xray config has egress-socks-in socks inbound"
  check_config_jq '.outbounds[] | select(.tag == "direct" and .protocol == "freedom")' \
    "xray config has direct/freedom outbound"
}

require_role
case "$ROLE" in
  relay) validate_relay ;;
  egress) validate_egress ;;
esac

if [[ "$FAILURES" -gt 0 ]]; then
  printf 'FAIL: %s check(s) failed.\n' "$FAILURES" >&2
  exit 1
fi

printf 'PASS: all %s checks passed.\n' "$ROLE"
