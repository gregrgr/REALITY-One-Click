map $ssl_preread_server_name $proxy_panel_backend {
    __PANEL_DOMAIN__ panel_https;
    default xray_reality;
}

upstream panel_https {
    server 127.0.0.1:8443;
}

upstream xray_reality {
    server __XRAY_LISTEN__:__XRAY_PORT__;
}

server {
    listen 443;
    listen [::]:443;
    proxy_pass $proxy_panel_backend;
    ssl_preread on;
}
