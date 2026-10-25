"""Lazy Telethon client plus lookup of chats the way a person names them."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from typing import Any

from telethon import TelegramClient, errors
from telethon.sessions import StringSession

from .config import Settings
from .formatting import display_name, entity_kind

DEVICE_MODEL = "Telegram MCP"
APP_VERSION = "0.1.0"
DIALOG_CACHE_SECONDS = 60
MAX_CANDIDATES = 10

_ID_RE = re.compile(r"^-?\d+$")
_PHONE_RE = re.compile(r"^\+\d{7,15}$")
_USERNAME_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{3,31}$")
_LINK_RE = re.compile(r"^(https?://)?(t|telegram)\.me/", re.IGNORECASE)
_SELF_ALIASES = {"me", "self", "saved", "избранное"}

ClientFactory = Callable[[Settings], TelegramClient]


class NotConfiguredError(RuntimeError):
    """Credentials are missing or the session is no longer authorized."""


class ChatNotFoundError(LookupError):
    pass


def make_client(settings: Settings) -> TelegramClient:
    if not settings.api_id or not settings.api_hash:
        raise NotConfiguredError(
            "Не заданы TELEGRAM_API_ID и TELEGRAM_API_HASH. Получите их на https://my.telegram.org/apps "
            "и запустите `python -m telegram_mcp.login`."
        )
    if not settings.session_string:
        raise NotConfiguredError("Нет TELEGRAM_SESSION_STRING. Запустите `python -m telegram_mcp.login`, чтобы войти.")
    return TelegramClient(
        StringSession(settings.session_string),
        settings.api_id,
        settings.api_hash,
        device_model=DEVICE_MODEL,
        app_version=APP_VERSION,
    )


class TelegramConnection:
    """Owns one Telethon client, connecting on first use."""

    def __init__(self, settings: Settings, client_factory: ClientFactory = make_client) -> None:
        self.settings = settings
        self._client_factory = client_factory
        self._client: TelegramClient | None = None
        self._lock = asyncio.Lock()
        self._connect_hooks: list[Callable[[TelegramClient], None]] = []
        self._dialogs: list[Any] = []
        self._dialogs_loaded_at = float("-inf")

    def on_connect(self, hook: Callable[[TelegramClient], None]) -> None:
        self._connect_hooks.append(hook)

    async def client(self) -> TelegramClient:
        async with self._lock:
            if self._client is None:
                client = self._client_factory(self.settings)
                await client.connect()
                if not await client.is_user_authorized():
                    await client.disconnect()
                    raise NotConfiguredError(
                        "Сессия Telegram не авторизована или была завершена. "
                        "Запустите `python -m telegram_mcp.login` ещё раз."
                    )
                for hook in self._connect_hooks:
                    hook(client)
                self._client = client
            elif not self._client.is_connected():
                await self._client.connect()
            return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None

    async def dialogs(self, refresh: bool = False) -> list[Any]:
        """All dialogs, cached briefly; loading them also fills Telethon's entity cache."""
        if refresh or time.monotonic() - self._dialogs_loaded_at > DIALOG_CACHE_SECONDS:
            client = await self.client()
            self._dialogs = list(await client.get_dialogs())
            self._dialogs_loaded_at = time.monotonic()
        return self._dialogs

    async def resolve(self, ref: str | int) -> Any:
        """Find a user, group or channel by id, @username, +phone, t.me link or display name."""
        client = await self.client()
        text = str(ref).strip()
        if not text:
            raise ChatNotFoundError("Не указан чат или пользователь.")

        if text.casefold() in _SELF_ALIASES:
            return await client.get_me()

        if _ID_RE.match(text):
            return await self._resolve_id(client, int(text))

        if text.startswith("@") or _LINK_RE.match(text) or _PHONE_RE.match(text):
            return await self._resolve_public(client, text)

        # A bare word is first looked up among the user's own chats, so "Anna"
        # finds the Anna they talk to rather than whoever owns the @Anna username.
        match = await self._match_dialog_name(text)
        if match is not None:
            return match
        if _USERNAME_RE.match(text):
            return await self._resolve_public(client, text)
        raise ChatNotFoundError(f"Чат или пользователь «{text}» не найден среди ваших диалогов.")

    async def _resolve_id(self, client: TelegramClient, peer_id: int) -> Any:
        try:
            return await client.get_entity(peer_id)
        except ValueError:
            pass
        for dialog in await self.dialogs(refresh=True):
            if dialog.id == peer_id:
                return dialog.entity
        raise ChatNotFoundError(f"Чат с id {peer_id} не найден среди ваших диалогов.")

    @staticmethod
    async def _resolve_public(client: TelegramClient, text: str) -> Any:
        try:
            return await client.get_entity(text)
        except (ValueError, errors.UsernameInvalidError, errors.UsernameNotOccupiedError) as exc:
            raise ChatNotFoundError(f"Не удалось найти «{text}»: {exc}") from exc

    async def _match_dialog_name(self, text: str) -> Any | None:
        needle = text.casefold().lstrip("@")
        dialogs = await self.dialogs()

        exact = [
            d
            for d in dialogs
            if (d.name or "").casefold() == needle or (getattr(d.entity, "username", None) or "").casefold() == needle
        ]
        candidates = exact or [d for d in dialogs if needle in (d.name or "").casefold()]

        if len(candidates) == 1:
            return candidates[0].entity
        if len(candidates) > 1:
            listed = "; ".join(
                f"{display_name(d.entity)} ({entity_kind(d.entity)}, id {d.id})" for d in candidates[:MAX_CANDIDATES]
            )
            more = f" и ещё {len(candidates) - MAX_CANDIDATES}" if len(candidates) > MAX_CANDIDATES else ""
            raise ChatNotFoundError(f"Под «{text}» подходит несколько чатов: {listed}{more}. Укажите id.")
        return None
