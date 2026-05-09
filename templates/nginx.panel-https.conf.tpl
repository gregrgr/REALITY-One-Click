server {
    listen 80;
    listen [::]:80;
    server_name __PANEL_DOMAIN__;

    location ^~ /.well-known/acme-challenge/ {
        root __ACME_WEBROOT__;
        default_type "text/plain";
    }

    location / {
        return 301 https://$host:__PANEL_HTTPS_PORT__$request_uri;
    }
}

server {
    listen __PANEL_HTTPS_PORT__ ssl http2;
    listen [::]:__PANEL_HTTPS_PORT__ ssl http2;
    server_name __PANEL_DOMAIN__;

    ssl_certificate /etc/letsencrypt/live/__PANEL_DOMAIN__/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/__PANEL_DOMAIN__/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:proxy_panel_ssl:10m;
    ssl_protocols TLSv1.2 TLSv1.3;

    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy no-referrer always;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
