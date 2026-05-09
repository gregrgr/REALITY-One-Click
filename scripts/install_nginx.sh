#!/usr/bin/env bash

install_nginx_base() {
  run_cmd install -d -m 0755 "$ACME_WEBROOT"
  run_cmd install -d -m 0755 /etc/nginx/stream-conf.d

  if ! grep -q 'stream-conf.d/\*.conf' /etc/nginx/nginx.conf 2>/dev/null; then
    if [[ "$DRY_RUN" == "1" ]]; then
      printf '[dry-run] add stream include to /etc/nginx/nginx.conf\n'
    else
      printf '\nstream {\n    include /etc/nginx/stream-conf.d/*.conf;\n}\n' >> /etc/nginx/nginx.conf
    fi
  fi
}

render_nginx_http_config() {
  render_template "$ROOT_DIR/templates/nginx.http.conf.tpl" /etc/nginx/sites-available/proxy-panel.conf
  run_cmd ln -sfn /etc/nginx/sites-available/proxy-panel.conf /etc/nginx/sites-enabled/proxy-panel.conf
  run_cmd rm -f /etc/nginx/sites-enabled/default
}

render_nginx_tls_config() {
  render_template "$ROOT_DIR/templates/nginx.panel-https.conf.tpl" /etc/nginx/sites-available/proxy-panel.conf
}

render_nginx_stream_config() {
  render_template "$ROOT_DIR/templates/nginx.stream.conf.tpl" /etc/nginx/stream-conf.d/reality.conf
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
