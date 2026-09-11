"""Redaction is a last defence; secrets are also rejected before model input."""
import json
import os
import re

KEY_PATTERN = re.compile(r"\bsk-" + r"[A-Za-z0-9_-]{16,}")
SENSITIVE = {"api_key", "authorization", "password", "secret", "cookie", "access_token"}


def clean(value):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if k.lower() in SENSITIVE else clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, str):
        value = KEY_PATTERN.sub("[REDACTED]", value)
        secret = os.environ.get("OPENAI_API_KEY")
        if secret:
            value = value.replace(secret, "[REDACTED]")
    return value


def reject_secrets(value):
    if clean(value) != value:
        raise ValueError("secret-like content rejected; remove it from the task/input")
