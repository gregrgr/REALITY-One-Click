from __future__ import annotations

import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


DEFAULT_PROBE_URL = "https://www.gstatic.com/generate_204"
DEFAULT_IP_CHECK_URL = "https://api.ipify.org"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_CACHE_SECONDS = 30.0
_CACHE: dict[str, Any] = {
    "key": None,
    "expires_at": 0.0,
    "value": None,
}


def parse_timeout(settings: dict[str, str]) -> float:
    try:
        timeout = float(settings.get("latency_timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS
    return min(max(timeout, 1.0), 30.0)


def parse_cache_seconds(settings: dict[str, str]) -> float:
    try:
        ttl = float(settings.get("latency_cache_seconds", DEFAULT_CACHE_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_CACHE_SECONDS
    return min(max(ttl, 0.0), 300.0)


def cache_key(settings: dict[str, str]) -> tuple[str, ...]:
    return (
        settings.get("latency_probe_url", DEFAULT_PROBE_URL),
        settings.get("latency_ip_check_url", DEFAULT_IP_CHECK_URL),
        settings.get("latency_timeout_seconds", str(DEFAULT_TIMEOUT_SECONDS)),
    )


def request_url(
    url: str,
    timeout: float,
    read_body: bool = False,
) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("latency probe URL must be http or https")

    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    start = time.monotonic()
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)

    try:
        if parsed.scheme == "https":
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=host)
            sock.settimeout(timeout)

        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "User-Agent: proxy-panel-latency/1.0\r\n"
            "Accept: */*\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        sock.sendall(request)

        payload = b""
        while b"\r\n\r\n" not in payload and len(payload) < 8192:
            chunk = sock.recv(4096)
            if not chunk:
                break
            payload += chunk

        latency_ms = round((time.monotonic() - start) * 1000)

        if read_body:
            while len(payload) < 16384:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                payload += chunk

        header, _, body = payload.partition(b"\r\n\r\n")
        status_code = 0
        first_line = header.splitlines()[0].decode("iso-8859-1", errors="replace") if header else ""
        parts = first_line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            status_code = int(parts[1])

        return {
            "latency_ms": latency_ms,
            "status_code": status_code,
            "body": body.decode("utf-8", errors="replace").strip(),
        }
    finally:
        sock.close()


def probe_exit_latency(settings: dict[str, str]) -> dict[str, Any]:
    timeout = parse_timeout(settings)
    probe_url = settings.get("latency_probe_url") or DEFAULT_PROBE_URL
    ip_url = settings.get("latency_ip_check_url") or DEFAULT_IP_CHECK_URL
    result: dict[str, Any] = {
        "status": "failed",
        "route": "direct",
        "probe_url": probe_url,
        "ip_check_url": ip_url,
        "timeout_seconds": timeout,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "exit_http_ms": None,
        "exit_ip": None,
        "http_status": None,
        "error": None,
        "ip_error": None,
    }

    try:
        probe = request_url(probe_url, timeout)
        result["exit_http_ms"] = probe["latency_ms"]
        result["http_status"] = probe["status_code"]
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"exit HTTP probe failed: {exc}"
        return result

    try:
        ip_probe = request_url(ip_url, timeout, read_body=True)
        if ip_probe["body"]:
            result["exit_ip"] = ip_probe["body"].splitlines()[0].strip()
    except Exception as exc:  # noqa: BLE001
        result["ip_error"] = str(exc)

    result["status"] = "ok"
    return result


def probe_exit_latency_cached(settings: dict[str, str]) -> dict[str, Any]:
    ttl = parse_cache_seconds(settings)
    key = cache_key(settings)
    now = time.monotonic()
    if ttl > 0 and _CACHE["key"] == key and _CACHE["value"] is not None and now < _CACHE["expires_at"]:
        cached = dict(_CACHE["value"])
        cached["cached"] = True
        return cached

    result = probe_exit_latency(settings)
    result["cached"] = False
    if ttl > 0:
        _CACHE["key"] = key
        _CACHE["value"] = dict(result)
        _CACHE["expires_at"] = now + ttl
    return result
