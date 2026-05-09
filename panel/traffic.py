from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TrafficStat:
    name: str
    uplink: int = 0
    downlink: int = 0

    @property
    def total(self) -> int:
        return self.uplink + self.downlink


def human_bytes(value: int) -> str:
    size = float(max(value, 0))
    units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{int(value)} B"


def query_user_traffic(settings: dict[str, str], users: list[Any], reset: bool = False) -> dict[str, TrafficStat]:
    raw_stats = query_xray_stats(settings, reset=reset)
    by_user = parse_user_stats(raw_stats)
    result: dict[str, TrafficStat] = {}

    for user in users:
        name = user["name"]
        values = by_user.get(name, {})
        result[name] = TrafficStat(
            name=name,
            uplink=values.get("uplink", 0),
            downlink=values.get("downlink", 0),
        )

    return result


def query_xray_stats(settings: dict[str, str], reset: bool = False) -> dict[str, int]:
    xray = shutil.which("xray") or "/usr/local/bin/xray"
    server = "{}:{}".format(
        settings.get("xray_api_host", "127.0.0.1"),
        settings.get("xray_api_port", "10085"),
    )

    commands = [
        [
            xray,
            "api",
            "statsquery",
            f"-server={server}",
            "-pattern=user>>>",
            f"-reset={str(reset).lower()}",
            "-json",
        ],
        [
            xray,
            "api",
            "statsquery",
            f"-server={server}",
            "-pattern=user>>>",
            f"-reset={str(reset).lower()}",
        ],
    ]

    last_error = ""
    for command in commands:
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=8,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            last_error = str(exc)
            continue

        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0:
            parsed = parse_stats_output(output)
            if parsed:
                return parsed
        last_error = output.strip()

    if last_error:
        return {}
    return {}


def parse_user_stats(stats: dict[str, int]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for name, value in stats.items():
        match = re.match(r"^user>>>(?P<user>.+?)>>>traffic>>>(?P<direction>uplink|downlink)$", name)
        if not match:
            continue
        user = match.group("user")
        direction = match.group("direction")
        result.setdefault(user, {})[direction] = value
    return result


def parse_stats_output(output: str) -> dict[str, int]:
    stripped = output.strip()
    if not stripped:
        return {}

    try:
        return parse_stats_json(json.loads(stripped))
    except json.JSONDecodeError:
        return parse_stats_text(stripped)


def parse_stats_json(payload: Any) -> dict[str, int]:
    stats: dict[str, int] = {}

    if isinstance(payload, dict):
        candidates = payload.get("stat") or payload.get("stats") or payload.get("response") or []
    elif isinstance(payload, list):
        candidates = payload
    else:
        candidates = []

    if isinstance(candidates, dict):
        candidates = candidates.get("stat") or candidates.get("stats") or []

    for item in candidates:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if isinstance(name, str) and isinstance(value, int):
            stats[name] = value

    return stats


def parse_stats_text(output: str) -> dict[str, int]:
    stats: dict[str, int] = {}
    current_name: str | None = None

    for line in output.splitlines():
        name_match = re.search(r'name:\s*"([^"]+)"', line)
        value_match = re.search(r"value:\s*([0-9]+)", line)
        compact_match = re.search(r"(user>>>[^ \t]+)\s+([0-9]+)", line)

        if compact_match:
            stats[compact_match.group(1)] = int(compact_match.group(2))
            current_name = None
            continue

        if name_match:
            current_name = name_match.group(1)
            if value_match:
                stats[current_name] = int(value_match.group(1))
                current_name = None
            continue

        if current_name and value_match:
            stats[current_name] = int(value_match.group(1))
            current_name = None

    return stats

