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
