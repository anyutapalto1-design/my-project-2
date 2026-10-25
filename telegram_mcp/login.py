"""Interactive login: creates TELEGRAM_SESSION_STRING and saves it to .env.

Run once in a terminal:  python -m telegram_mcp.login
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os

from dotenv import set_key
from telethon import TelegramClient
from telethon.sessions import StringSession

from .config import ENV_FILE, Settings, load_env_file
from .connection import APP_VERSION, DEVICE_MODEL


def _ask(prompt: str) -> str:
    value = ""
    while not value:
        value = input(prompt).strip()
    return value


def _save_env(values: dict[str, str]) -> None:
    ENV_FILE.touch(mode=0o600, exist_ok=True)
    os.chmod(ENV_FILE, 0o600)
    for key, value in values.items():
        set_key(ENV_FILE, key, value, quote_mode="never")


async def login(print_only: bool) -> None:
    load_env_file()
    settings = Settings.from_env()

    print("Вход в Telegram для MCP-сервера.")
    print("API ID и API hash берутся на https://my.telegram.org/apps (раздел API development tools).\n")
    api_id = settings.api_id or int(_ask("API ID: "))
    api_hash = settings.api_hash or _ask("API hash: ")

    client = TelegramClient(StringSession(), api_id, api_hash, device_model=DEVICE_MODEL, app_version=APP_VERSION)
    await client.start(
        phone=lambda: _ask("Номер телефона в международном формате (+7...): "),
        code_callback=lambda: _ask("Код подтверждения из Telegram: "),
        password=lambda: getpass.getpass("Пароль двухэтапной аутентификации: "),
    )
    me = await client.get_me()
    session_string = client.session.save()
    await client.disconnect()

    username = f" (@{me.username})" if me.username else ""
    print(f"\nГотово, вы вошли как {me.first_name or ''} {me.last_name or ''}{username}".rstrip())

    values = {
        "TELEGRAM_API_ID": str(api_id),
        "TELEGRAM_API_HASH": api_hash,
        "TELEGRAM_SESSION_STRING": session_string,
    }
    if print_only:
        print("\nНикому не показывайте эту строку: она даёт полный доступ к аккаунту.\n")
        for key, value in values.items():
            print(f"{key}={value}")
        return

    _save_env(values)
    print(f"Данные сохранены в {ENV_FILE} (доступ только для вашего пользователя).")
    print("Завершить эту сессию можно в Telegram: Настройки → Устройства → «Telegram MCP».")


def main() -> None:
    parser = argparse.ArgumentParser(description="Войти в Telegram и получить строку сессии для MCP-сервера.")
    parser.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="напечатать данные в терминал вместо записи в .env",
    )
    args = parser.parse_args()
    asyncio.run(login(args.print_only))


if __name__ == "__main__":
    main()
