"""Settings read from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

TRANSCRIPTION_METHODS = ("auto", "telegram", "whisper")
_TRUE_VALUES = {"1", "true", "yes", "on", "да"}


def load_env_file() -> None:
    """Load `.env` from the project root without overriding real env vars."""
    load_dotenv(ENV_FILE, override=False)


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUE_VALUES


@dataclass(frozen=True)
class Settings:
    api_id: int | None
    api_hash: str | None
    session_string: str | None
    read_only: bool
    download_dir: Path
    transcription: str
    whisper_model: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env

        api_id_raw = (env.get("TELEGRAM_API_ID") or "").strip()
        if api_id_raw and not api_id_raw.isdigit():
            raise ValueError("TELEGRAM_API_ID должен быть числом (см. https://my.telegram.org/apps)")

        transcription = (env.get("TELEGRAM_TRANSCRIPTION") or "auto").strip().lower()
        if transcription not in TRANSCRIPTION_METHODS:
            raise ValueError(f"TELEGRAM_TRANSCRIPTION должен быть одним из: {', '.join(TRANSCRIPTION_METHODS)}")

        download_dir = env.get("TELEGRAM_DOWNLOAD_DIR") or str(Path.home() / "Downloads" / "telegram-mcp")

        return cls(
            api_id=int(api_id_raw) if api_id_raw else None,
            api_hash=(env.get("TELEGRAM_API_HASH") or "").strip() or None,
            session_string=(env.get("TELEGRAM_SESSION_STRING") or "").strip() or None,
            read_only=_flag(env.get("TELEGRAM_READ_ONLY")),
            download_dir=Path(download_dir).expanduser(),
            transcription=transcription,
            whisper_model=(env.get("WHISPER_MODEL") or "small").strip(),
        )
