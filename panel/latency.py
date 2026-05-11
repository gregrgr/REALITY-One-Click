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


def parse_timeout(settings: dict[str, str]) -> float:
    try:
        timeout = float(settings.get("latency_timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS
    return min(max(timeout, 1.0), 30.0)


def read_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise OSError("unexpected EOF during SOCKS handshake")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def socks5_connect(
    proxy_host: str,
    proxy_port: int,
    target_host: str,
    target_port: int,
    timeout: float,
) -> socket.socket:
    sock = socket.create_connection((proxy_host, proxy_port), timeout=timeout)
    sock.settimeout(timeout)
    try:
        sock.sendall(b"\x05\x01\x00")
        method = read_exact(sock, 2)
        if method != b"\x05\x00":
            raise OSError("SOCKS server did not accept no-auth mode")

        host_bytes = target_host.encode("idna")
        if len(host_bytes) > 255:
            raise OSError("target host is too long for SOCKS5")
        request = (
            b"\x05\x01\x00\x03"
            + bytes([len(host_bytes)])
            + host_bytes
            + int(target_port).to_bytes(2, "big")
        )
        sock.sendall(request)
        header = read_exact(sock, 4)
        if header[1] != 0:
            raise OSError(f"SOCKS connect failed with code {header[1]}")

        atyp = header[3]
        if atyp == 1:
            read_exact(sock, 4)
        elif atyp == 3:
            length = read_exact(sock, 1)[0]
            read_exact(sock, length)
        elif atyp == 4:
            read_exact(sock, 16)
        else:
            raise OSError(f"SOCKS response has invalid address type {atyp}")
        read_exact(sock, 2)
        return sock
    except Exception:
        sock.close()
        raise


def measure_tcp_connect(host: str, port: int, timeout: float) -> int:
    start = time.monotonic()
    with socket.create_connection((host, port), timeout=timeout):
        return round((time.monotonic() - start) * 1000)


def request_url(
    url: str,
    timeout: float,
    socks_proxy: tuple[str, int] | None = None,
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
    if socks_proxy:
        sock = socks5_connect(socks_proxy[0], socks_proxy[1], host, port, timeout)
    else:
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
    role = settings.get("node_role", "single") or "single"
    timeout = parse_timeout(settings)
    probe_url = settings.get("latency_probe_url") or DEFAULT_PROBE_URL
    ip_url = settings.get("latency_ip_check_url") or DEFAULT_IP_CHECK_URL
    result: dict[str, Any] = {
        "status": "failed",
        "node_role": role,
        "route": "direct" if role == "single" else "relay-egress-socks",
        "probe_url": probe_url,
        "ip_check_url": ip_url,
        "timeout_seconds": timeout,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "backend": None,
        "backend_tcp_ms": None,
        "exit_http_ms": None,
        "exit_ip": None,
        "http_status": None,
        "error": None,
        "ip_error": None,
    }

    if role == "egress":
        result["status"] = "skipped"
        result["route"] = "egress-local"
        result["error"] = "egress node does not run the management panel."
        return result

    socks_proxy: tuple[str, int] | None = None
    if role == "relay":
        protocol = settings.get("egress_backend_protocol", "socks") or "socks"
        if protocol != "socks":
            result["error"] = f"unsupported egress backend protocol: {protocol}"
            return result
        host = settings.get("egress_tailscale_ip", "").strip()
        if not host:
            result["error"] = "egress_tailscale_ip is required for relay latency checks"
            return result
        try:
            port = int(settings.get("egress_backend_port", "10808"))
        except ValueError:
            result["error"] = "egress_backend_port must be numeric"
            return result

        result["backend"] = f"{host}:{port}"
        try:
            result["backend_tcp_ms"] = measure_tcp_connect(host, port, timeout)
        except Exception as exc:  # noqa: BLE001 - surface operational failures in the panel.
            result["error"] = f"egress backend TCP check failed: {exc}"
            return result
        socks_proxy = (host, port)

    try:
        probe = request_url(probe_url, timeout, socks_proxy=socks_proxy)
        result["exit_http_ms"] = probe["latency_ms"]
        result["http_status"] = probe["status_code"]
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"exit HTTP probe failed: {exc}"
        return result

    try:
        ip_probe = request_url(ip_url, timeout, socks_proxy=socks_proxy, read_body=True)
        if ip_probe["body"]:
            result["exit_ip"] = ip_probe["body"].splitlines()[0].strip()
    except Exception as exc:  # noqa: BLE001
        result["ip_error"] = str(exc)

    result["status"] = "ok"
    return result
