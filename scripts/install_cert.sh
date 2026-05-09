#!/usr/bin/env bash

install_certificate() {
  local cert_path="/etc/letsencrypt/live/${PANEL_DOMAIN}/fullchain.pem"
  if [[ -s "$cert_path" ]]; then
    log "Certificate already exists for ${PANEL_DOMAIN}"
    install_cert_deploy_hook
    return
  fi

  local staging_arg=()
  if [[ "${ACME_STAGING:-0}" == "1" ]]; then
    staging_arg=(--staging)
  fi

  if [[ "${ACME_CHALLENGE:-http}" == "cloudflare" ]]; then
    install_cloudflare_credentials
    run_cmd certbot certonly \
      --dns-cloudflare \
      --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
      --dns-cloudflare-propagation-seconds "${CLOUDFLARE_PROPAGATION_SECONDS:-60}" \
      -d "$PANEL_DOMAIN" \
      --email "$ACME_EMAIL" \
      --agree-tos \
      --non-interactive \
      --keep-until-expiring \
      "${staging_arg[@]}"
  else
    run_cmd certbot certonly \
      --webroot \
      -w "$ACME_WEBROOT" \
      -d "$PANEL_DOMAIN" \
      --email "$ACME_EMAIL" \
      --agree-tos \
      --non-interactive \
      --keep-until-expiring \
      "${staging_arg[@]}"
  fi

  install_cert_deploy_hook
}

install_cloudflare_credentials() {
  [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]] || die "CLOUDFLARE_API_TOKEN is required."

  run_cmd install -d -m 0700 /etc/letsencrypt
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] write /etc/letsencrypt/cloudflare.ini\n'
    return
  fi

  cat > /etc/letsencrypt/cloudflare.ini <<EOF
dns_cloudflare_api_token = ${CLOUDFLARE_API_TOKEN}
EOF
  chmod 0600 /etc/letsencrypt/cloudflare.ini
}

install_cert_deploy_hook() {
  run_cmd install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] install certbot deploy hook\n'
    return
  fi

  cat > /etc/letsencrypt/renewal-hooks/deploy/proxy-panel-nginx-reload.sh <<'EOF'
#!/usr/bin/env bash
set -e
systemctl reload nginx >/dev/null 2>&1 || true
EOF
  chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/proxy-panel-nginx-reload.sh
}
