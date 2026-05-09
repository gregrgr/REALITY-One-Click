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

  run_cmd certbot certonly \
    --webroot \
    -w "$ACME_WEBROOT" \
    -d "$PANEL_DOMAIN" \
    --email "$ACME_EMAIL" \
    --agree-tos \
    --non-interactive \
    --keep-until-expiring \
    "${staging_arg[@]}"

  install_cert_deploy_hook
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
