"""Loads and validates configuration from .env (no external dependency)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REQUIRED_VARS = [
    "GEMINI_API_KEY",
    "BREVO_SMTP_HOST",
    "BREVO_SMTP_PORT",
    "BREVO_SMTP_USER",
    "BREVO_SMTP_PASSWORD",
    "EMAIL_FROM",
    "EMAIL_TO",
]


def _parse_env_file(path: Path) -> dict:
    values = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    gemini_api_key: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    email_from: str
    email_to: str


def load_config(env_path: Path | None = None) -> Config:
    project_root = Path(__file__).resolve().parent.parent
    env_path = env_path or project_root / ".env"

    values = _parse_env_file(env_path)
    # Real environment variables take precedence over the .env file.
    for key in REQUIRED_VARS:
        if key in os.environ:
            values[key] = os.environ[key]

    missing = [key for key in REQUIRED_VARS if not values.get(key)]
    if missing:
        raise ConfigError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + f". Checked {env_path} and process environment. "
            "See .env.example for the expected keys."
        )

    try:
        smtp_port = int(values["BREVO_SMTP_PORT"])
    except ValueError as exc:
        raise ConfigError(
            f"BREVO_SMTP_PORT must be an integer, got {values['BREVO_SMTP_PORT']!r}"
        ) from exc

    return Config(
        gemini_api_key=values["GEMINI_API_KEY"],
        smtp_host=values["BREVO_SMTP_HOST"],
        smtp_port=smtp_port,
        smtp_user=values["BREVO_SMTP_USER"],
        smtp_password=values["BREVO_SMTP_PASSWORD"],
        email_from=values["EMAIL_FROM"],
        email_to=values["EMAIL_TO"],
    )
