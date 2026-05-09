from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import Any

from itsdangerous import BadSignature, URLSafeTimedSerializer


PBKDF2_ITERATIONS = 260_000


def random_token(byte_count: int = 32) -> str:
    return secrets.token_urlsafe(byte_count)


def random_uuid() -> str:
    import uuid

    return str(uuid.uuid4())


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = base64.b64decode(salt_text)
        expected = base64.b64decode(digest_text)
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt="proxy-panel-session")


def sign_session(secret_key: str, payload: dict[str, Any]) -> str:
    return serializer(secret_key).dumps(payload)


def load_session(secret_key: str, token: str, max_age: int = 60 * 60 * 12) -> dict[str, Any] | None:
    try:
        data = serializer(secret_key).loads(token, max_age=max_age)
    except BadSignature:
        return None
    return data if isinstance(data, dict) else None

