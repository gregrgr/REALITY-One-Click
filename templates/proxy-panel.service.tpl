[Unit]
Description=Proxy Panel API and subscription service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=__ENV_FILE__
WorkingDirectory=__OPT_DIR__
ExecStart=__OPT_DIR__/.venv/bin/uvicorn panel.app:app --host 127.0.0.1 --port 8080
Restart=on-failure
RestartSec=3
UMask=0077

[Install]
WantedBy=multi-user.target
