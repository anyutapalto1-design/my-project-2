"""A stand-in for TelegramClient so tools can be tested without a real account."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from telethon import utils
from telethon.tl import types

from telegram_mcp.config import Settings
from telegram_mcp.connection import TelegramConnection

DATE = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def make_user(user_id: int, first_name: str, username: str | None = None, **kwargs: Any) -> types.User:
    return types.User(id=user_id, first_name=first_name, username=username, access_hash=user_id, **kwargs)


def make_group(chat_id: int, title: str) -> types.Chat:
    return types.Chat(id=chat_id, title=title, photo=types.ChatPhotoEmpty(), participants_count=3, date=DATE, version=1)


def make_message(message_id: int, peer: Any, text: str = "", **kwargs: Any) -> types.Message:
    return types.Message(id=message_id, peer_id=peer, date=DATE, message=text, **kwargs)


def voice_media(duration: int = 7) -> types.MessageMediaDocument:
    document = types.Document(
        id=1,
        access_hash=1,
        file_reference=b"",
        date=DATE,
        mime_type="audio/ogg",
        size=2048,
        dc_id=2,
        attributes=[types.DocumentAttributeAudio(duration=duration, voice=True)],
    )
    return types.MessageMediaDocument(document=document)


def make_dialog(entity: Any, unread: int = 0, last: types.Message | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=utils.get_peer_id(entity),
        entity=entity,
        name=utils.get_display_name(entity),
        unread_count=unread,
        unread_mentions_count=0,
        pinned=False,
        archived=False,
        message=last,
        dialog=SimpleNamespace(notify_settings=None),
        is_user=isinstance(entity, types.User),
        is_group=isinstance(entity, types.Chat),
        is_channel=isinstance(entity, types.Channel),
    )


class FakeClient:
    def __init__(self, me: types.User, dialogs: list[SimpleNamespace], messages: dict[int, list[Any]]) -> None:
        self.me = me
        self.dialogs = dialogs
        self.messages = messages
        self.cache: dict[int, Any] = {utils.get_peer_id(me): me}
        self.public: dict[str, Any] = {}
        self.sent: list[tuple[Any, str, dict[str, Any]]] = []
        self.requests: list[Any] = []
        self.handlers: list[Any] = []
        self.connected = False
        self.authorized = True

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    async def is_user_authorized(self) -> bool:
        return self.authorized

    def add_event_handler(self, callback: Any, event: Any) -> None:
        self.handlers.append((callback, event))

    async def get_me(self) -> types.User:
        return self.me

    async def get_dialogs(self) -> list[SimpleNamespace]:
        for dialog in self.dialogs:
            self.cache[dialog.id] = dialog.entity
        return self.dialogs

    async def iter_dialogs(self, archived: bool = False):
        for dialog in self.dialogs:
            yield dialog

    async def get_entity(self, ref: Any) -> Any:
        if isinstance(ref, int):
            if ref in self.cache:
                return self.cache[ref]
            raise ValueError(f"Could not find the input entity for {ref}")
        key = ref.lstrip("@").removeprefix("https://t.me/").casefold()
        if key in self.public:
            return self.public[key]
        raise ValueError(f'No user has "{ref}" as username')

    async def iter_messages(self, entity: Any, limit: int = 100, offset_id: int = 0, **kwargs: Any):
        history = self.messages.get(utils.get_peer_id(entity), [])
        newest_first = sorted(history, key=lambda message: message.id, reverse=True)
        if offset_id:
            newest_first = [message for message in newest_first if message.id < offset_id]
        for message in newest_first[:limit]:
            yield message

    async def get_messages(self, entity: Any, ids: int) -> Any:
        for message in self.messages.get(utils.get_peer_id(entity), []):
            if message.id == ids:
                return message
        return None

    async def send_message(self, entity: Any, text: str, **kwargs: Any) -> types.Message:
        self.sent.append((entity, text, kwargs))
        return make_message(999, utils.get_peer(entity), text, out=True)

    async def __call__(self, request: Any) -> Any:
        self.requests.append(request)
        raise AssertionError(f"Unexpected request {type(request).__name__}")


@pytest.fixture
def people() -> dict[str, Any]:
    return {
        "me": make_user(1, "Аня", "anya_me", is_self=True),
        "mom": make_user(2, "Мама"),
        "anna": make_user(3, "Anna", "anna_k", contact=True),
        "anna_work": make_user(4, "Anna Work"),
        "family": make_group(50, "Семья"),
    }


@pytest.fixture
def fake_client(people: dict[str, Any]) -> FakeClient:
    mom_peer = types.PeerUser(people["mom"].id)
    history = [
        make_message(10, mom_peer, "Привет! Как дела?"),
        make_message(11, mom_peer, "", media=voice_media()),
        make_message(12, mom_peer, "Позвони, как сможешь", reply_to=types.MessageReplyHeader(reply_to_msg_id=10)),
    ]
    dialogs = [
        make_dialog(people["mom"], unread=2, last=history[-1]),
        make_dialog(people["anna"]),
        make_dialog(people["anna_work"]),
        make_dialog(people["family"]),
    ]
    return FakeClient(people["me"], dialogs, {people["mom"].id: history})


@pytest.fixture
def settings(tmp_path: Any) -> Settings:
    return Settings.from_env({"TELEGRAM_DOWNLOAD_DIR": str(tmp_path / "downloads")})


@pytest.fixture
def connection(settings: Settings, fake_client: FakeClient) -> TelegramConnection:
    return TelegramConnection(settings, client_factory=lambda _: fake_client)
