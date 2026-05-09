from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeSettings:
    db_path: str
    xray_config_path: str
    secret_key: str
    public_base: str


def get_runtime_settings() -> RuntimeSettings:
    return RuntimeSettings(
        db_path=os.getenv("PROXY_PANEL_DB", "/var/lib/proxy-panel/panel.db"),
        xray_config_path=os.getenv("PROXY_PANEL_CONFIG", "/etc/xray/config.json"),
        secret_key=os.getenv("PROXY_PANEL_SECRET_KEY", "change-me-before-production"),
        public_base=os.getenv("PROXY_PANEL_PUBLIC_BASE", "https://localhost"),
    )

