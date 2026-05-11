#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT_DIR/scripts/common.sh"

if [[ -r "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

section() {
  printf '\n== %s ==\n' "$1"
}

run_optional() {
  local label="$1"
  shift
  section "$label"
  if "$@"; then
    return 0
  fi
  printf 'command failed: %s\n' "$*" >&2
}

section "runtime"
printf 'date: %s\n' "$(date -Is)"
printf 'node_role: %s\n' "${NODE_ROLE:-unknown}"
printf 'egress: %s:%s\n' "${EGRESS_TAILSCALE_IP:-unset}" "${EGRESS_BACKEND_PORT:-10808}"
printf 'loadavg: %s\n' "$(cat /proc/loadavg 2>/dev/null || true)"
printf 'nproc: %s\n' "$(nproc 2>/dev/null || true)"

section "top cpu processes"
ps -eo pid,ppid,comm,%cpu,%mem,args --sort=-%cpu | head -30 || true

section "service state"
for service in xray proxy-panel nginx tailscaled; do
  if command_exists systemctl; then
    printf '%s: ' "$service"
    systemctl is-active "$service" 2>/dev/null || true
  fi
done

if command_exists ss; then
  section "listening ports"
  ss -lntp | grep -E ':(80|443|8443|8080|10085|10808)\b' || true

  section "connection summary"
  ss -Hantp | awk '{print $1}' | sort | uniq -c | sort -nr || true

  section "top remote endpoints"
  ss -Hantp | awk '{print $5}' | sed 's/\[//;s/\]//' | sed 's/:[0-9]*$//' | sort | uniq -c | sort -nr | head -30 || true
fi

if command_exists jq && [[ -r "${PROXY_PANEL_CONFIG:-/usr/local/etc/xray/config.json}" ]]; then
  section "xray relay routing"
  jq '(.routing.rules), (.outbounds[] | select(.tag=="egress-via-tailscale"))' "${PROXY_PANEL_CONFIG:-/usr/local/etc/xray/config.json}" || true
fi

if command_exists tailscale; then
  run_optional "tailscale status" tailscale status
  run_optional "tailscale netcheck" tailscale netcheck
fi

if command_exists proxy-panel; then
  run_optional "proxy-panel latency" proxy-panel latency
  run_optional "proxy-panel traffic" proxy-panel traffic
fi

if command_exists journalctl; then
  run_optional "recent xray logs" journalctl -u xray -n 80 --no-pager
  run_optional "recent proxy-panel logs" journalctl -u proxy-panel -n 60 --no-pager
fi
