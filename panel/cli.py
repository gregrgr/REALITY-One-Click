from __future__ import annotations

import argparse
import sys

from .database import Database
from .service import restart_service, systemctl_is_active
from .settings import get_runtime_settings
from .subscriptions import vless_uri
from .xray_config import write_xray_config


def db() -> Database:
    runtime = get_runtime_settings()
    database = Database(runtime.db_path)
    database.init()
    return database


def parse_setting_args(values: list[str] | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values or []:
        if "=" not in item:
            raise SystemExit(f"Invalid --setting value: {item}")
        key, value = item.split("=", 1)
        parsed[key] = value
    return parsed


def render_config(database: Database | None = None) -> None:
    runtime = get_runtime_settings()
    database = database or db()
    write_xray_config(
        runtime.xray_config_path,
        database.get_settings(),
        database.enabled_users(),
    )


def print_user(user, settings: dict[str, str]) -> None:
    base = get_runtime_settings().public_base.rstrip("/")
    print(f"name: {user['name']}")
    print(f"uuid: {user['uuid']}")
    print(f"enabled: {bool(user['enabled'])}")
    print(f"clash: {base}/sub/{user['subscription_token']}/clash.yaml")
    print(f"vless-sub: {base}/sub/{user['subscription_token']}/vless.txt")
    print(f"vless-uri: {vless_uri(settings, user)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="proxy-panel")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init")
    init_parser.add_argument("--admin-user", required=True)
    init_parser.add_argument("--admin-password", required=True)
    init_parser.add_argument("--setting", action="append", default=[])

    ensure_user = sub.add_parser("ensure-user")
    ensure_user.add_argument("name")

    add_user = sub.add_parser("add-user")
    add_user.add_argument("name")

    sub.add_parser("list-users")

    for command_name in ("enable-user", "disable-user", "delete-user", "reset-token", "reset-uuid", "show-sub"):
        command = sub.add_parser(command_name)
        command.add_argument("name")

    sub.add_parser("render")
    sub.add_parser("restart")
    sub.add_parser("status")

    args = parser.parse_args(argv)
    database = db()

    if args.command == "init":
        database.upsert_admin(args.admin_user, args.admin_password)
        database.set_settings(parse_setting_args(args.setting))
        print("initialized")
        return 0

    if args.command == "ensure-user":
        user = database.ensure_user(args.name)
        print_user(user, database.get_settings())
        return 0

    if args.command == "add-user":
        user = database.create_user(args.name)
        render_config(database)
        print_user(user, database.get_settings())
        return 0

    if args.command == "list-users":
        for user in database.list_users():
            state = "enabled" if user["enabled"] else "disabled"
            print(f"{user['id']}\t{user['name']}\t{state}\t{user['uuid']}")
        return 0

    if args.command in {"enable-user", "disable-user", "delete-user", "reset-token", "reset-uuid", "show-sub"}:
        user = database.get_user_by_name(args.name)
        if not user:
            print(f"user not found: {args.name}", file=sys.stderr)
            return 1

        if args.command == "enable-user":
            database.set_user_enabled(user["id"], True)
            render_config(database)
            print("enabled")
            return 0
        if args.command == "disable-user":
            database.set_user_enabled(user["id"], False)
            render_config(database)
            print("disabled")
            return 0
        if args.command == "delete-user":
            database.delete_user(user["id"])
            render_config(database)
            print("deleted")
            return 0
        if args.command == "reset-token":
            updated = database.reset_user_token(user["id"])
            if updated:
                print_user(updated, database.get_settings())
            return 0
        if args.command == "reset-uuid":
            updated = database.reset_user_uuid(user["id"])
            render_config(database)
            if updated:
                print_user(updated, database.get_settings())
            return 0
        if args.command == "show-sub":
            print_user(user, database.get_settings())
            return 0

    if args.command == "render":
        render_config(database)
        print("rendered")
        return 0

    if args.command == "restart":
        render_config(database)
        ok, output = restart_service("xray")
        print(output or ("restarted" if ok else "failed"))
        return 0 if ok else 1

    if args.command == "status":
        for service in ("xray", "nginx", "proxy-panel"):
            print(f"{service}: {systemctl_is_active(service)}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

