#!/usr/bin/env bash

install_nginx_base() {
  run_cmd install -d -m 0755 "$ACME_WEBROOT"
}

render_nginx_http_config() {
  render_template "$ROOT_DIR/templates/nginx.http.conf.tpl" /etc/nginx/sites-available/proxy-panel.conf
  run_cmd ln -sfn /etc/nginx/sites-available/proxy-panel.conf /etc/nginx/sites-enabled/proxy-panel.conf
  run_cmd rm -f /etc/nginx/sites-enabled/default
}

render_nginx_tls_config() {
  render_template "$ROOT_DIR/templates/nginx.panel-https.conf.tpl" /etc/nginx/sites-available/proxy-panel.conf
}

disable_nginx_stream_config() {
  run_cmd rm -f /etc/nginx/stream-conf.d/reality.conf
}

reload_or_start_nginx() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] nginx -t && systemctl reload nginx\n'
    return
  fi

  nginx -t
  systemctl enable nginx
  if systemctl is-active --quiet nginx; then
    systemctl reload nginx
  else
    systemctl restart nginx
  fi
}
