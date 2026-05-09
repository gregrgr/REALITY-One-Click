from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from .database import Database
from .security import load_session, sign_session, verify_password
from .service import recent_journal, restart_service, systemctl_is_active
from .settings import RuntimeSettings, get_runtime_settings
from .subscriptions import clash_yaml, vless_uri
from .xray_config import write_xray_config


runtime = get_runtime_settings()
database = Database(runtime.db_path)
templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))

app = FastAPI(title="Proxy Panel", docs_url=None, redoc_url=None)


@app.on_event("startup")
def startup() -> None:
    database.init()


def session_from_request(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get("proxy_panel_session")
    if not token:
        return None
    return load_session(runtime.secret_key, token)


def require_admin(request: Request) -> dict[str, Any]:
    session = session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session


def wants_secure_cookie(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    return request.url.scheme == "https" or forwarded_proto == "https"


def render_and_restart_xray() -> tuple[bool, str]:
    write_xray_config(
        runtime.xray_config_path,
        database.get_settings(),
        database.enabled_users(),
    )
    return restart_service("xray")


def redirect_with_message(message: str) -> RedirectResponse:
    return RedirectResponse("/?" + urlencode({"message": message}), status_code=303)


def dashboard_context(request: Request, message: str | None = None) -> dict[str, Any]:
    settings = database.get_settings()
    base = runtime.public_base.rstrip("/")
    users = []
    for row in database.list_users():
        user = dict(row)
        user["clash_url"] = f"{base}/sub/{row['subscription_token']}/clash.yaml"
        user["vless_sub_url"] = f"{base}/sub/{row['subscription_token']}/vless.txt"
        user["vless_uri"] = vless_uri(settings, row)
        users.append(user)

    return {
        "request": request,
        "message": message,
        "users": users,
        "settings": settings,
        "services": {
            "xray": systemctl_is_active("xray"),
            "nginx": systemctl_is_active("nginx"),
            "proxy-panel": systemctl_is_active("proxy-panel"),
        },
        "logs": {
            "xray": recent_journal("xray", 20),
            "proxy-panel": recent_journal("proxy-panel", 20),
        },
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    if session_from_request(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> Response:
    admin = database.get_admin_by_username(username)
    if not admin or not verify_password(password, admin["password_hash"]):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "用户名或密码错误"},
            status_code=401,
        )

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "proxy_panel_session",
        sign_session(runtime.secret_key, {"username": username}),
        httponly=True,
        secure=wants_secure_cookie(request),
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return response


@app.post("/logout")
def logout(_: dict[str, Any] = Depends(require_admin)) -> RedirectResponse:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("proxy_panel_session")
    return response


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> Response:
    if not session_from_request(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(
        "dashboard.html",
        dashboard_context(request, request.query_params.get("message")),
    )


@app.post("/users")
def create_user(
    request: Request,
    name: str = Form(...),
    _: dict[str, Any] = Depends(require_admin),
) -> RedirectResponse:
    clean_name = name.strip()
    if not clean_name:
        return redirect_with_message("用户名不能为空")
    database.create_user(clean_name)
    ok, output = render_and_restart_xray()
    message = "用户已创建" if ok else f"用户已创建，但重启 Xray 失败：{output}"
    return redirect_with_message(message)


@app.post("/users/{user_id}/toggle")
def toggle_user(
    user_id: int,
    _: dict[str, Any] = Depends(require_admin),
) -> RedirectResponse:
    user = database.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404)
    database.set_user_enabled(user_id, not bool(user["enabled"]))
    ok, output = render_and_restart_xray()
    message = "用户状态已更新" if ok else f"状态已更新，但重启 Xray 失败：{output}"
    return redirect_with_message(message)


@app.post("/users/{user_id}/delete")
def delete_user(
    user_id: int,
    _: dict[str, Any] = Depends(require_admin),
) -> RedirectResponse:
    database.delete_user(user_id)
    ok, output = render_and_restart_xray()
    message = "用户已删除" if ok else f"用户已删除，但重启 Xray 失败：{output}"
    return redirect_with_message(message)


@app.post("/users/{user_id}/reset-token")
def reset_token(
    user_id: int,
    _: dict[str, Any] = Depends(require_admin),
) -> RedirectResponse:
    database.reset_user_token(user_id)
    return redirect_with_message("订阅 Token 已重置")


@app.post("/users/{user_id}/reset-uuid")
def reset_uuid(
    user_id: int,
    _: dict[str, Any] = Depends(require_admin),
) -> RedirectResponse:
    database.reset_user_uuid(user_id)
    ok, output = render_and_restart_xray()
    message = "UUID 已重置" if ok else f"UUID 已重置，但重启 Xray 失败：{output}"
    return redirect_with_message(message)


@app.post("/xray/reload")
def reload_xray(_: dict[str, Any] = Depends(require_admin)) -> RedirectResponse:
    ok, output = render_and_restart_xray()
    message = "Xray 已重新加载" if ok else f"重启 Xray 失败：{output}"
    return redirect_with_message(message)


@app.get("/api/status")
def api_status(_: dict[str, Any] = Depends(require_admin)) -> dict[str, str]:
    return {
        "xray": systemctl_is_active("xray"),
        "nginx": systemctl_is_active("nginx"),
        "proxy-panel": systemctl_is_active("proxy-panel"),
    }


@app.get("/sub/{token}/clash.yaml")
def clash_subscription(token: str) -> PlainTextResponse:
    user = database.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=404)
    return PlainTextResponse(
        clash_yaml(database.get_settings(), user),
        media_type="application/x-yaml; charset=utf-8",
    )


@app.get("/sub/{token}/vless.txt")
def vless_subscription(token: str) -> PlainTextResponse:
    user = database.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=404)
    return PlainTextResponse(
        vless_uri(database.get_settings(), user) + "\n",
        media_type="text/plain; charset=utf-8",
    )
