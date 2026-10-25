from pathlib import Path

import pytest

from telegram_mcp.config import Settings


def test_defaults() -> None:
    settings = Settings.from_env({})
    assert settings.api_id is None
    assert settings.session_string is None
    assert settings.read_only is False
    assert settings.transcription == "auto"
    assert settings.download_dir == Path.home() / "Downloads" / "telegram-mcp"


def test_values_are_parsed() -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_API_ID": " 12345 ",
            "TELEGRAM_API_HASH": "abc",
            "TELEGRAM_SESSION_STRING": "1Aa==",
            "TELEGRAM_READ_ONLY": "Yes",
            "TELEGRAM_TRANSCRIPTION": "whisper",
        }
    )
    assert settings.api_id == 12345
    assert settings.api_hash == "abc"
    assert settings.session_string == "1Aa=="
    assert settings.read_only is True
    assert settings.transcription == "whisper"


@pytest.mark.parametrize(
    "env",
    [{"TELEGRAM_API_ID": "not-a-number"}, {"TELEGRAM_TRANSCRIPTION": "magic"}],
)
def test_invalid_values_are_rejected(env: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        Settings.from_env(env)
