from telethon.tl import types

from telegram_mcp.formatting import format_dialog, format_entity, format_message, media_info

from .conftest import make_dialog, make_group, make_message, make_user, voice_media


def test_text_message_drops_empty_fields() -> None:
    message = make_message(5, types.PeerUser(2), "Привет", reply_to=types.MessageReplyHeader(reply_to_msg_id=3))
    data = format_message(message)
    assert data["id"] == 5
    assert data["text"] == "Привет"
    assert data["reply_to"] == 3
    assert data["date"].startswith("2026-10-01")
    assert "media" not in data
    assert "out" not in data


def test_voice_message_reports_duration() -> None:
    message = make_message(6, types.PeerUser(2), media=voice_media(duration=42))
    assert media_info(message) == {"type": "voice", "mime_type": "audio/ogg", "size": 2048, "duration": 42}


def test_link_preview_is_not_reported_as_photo() -> None:
    page = types.WebPage(
        id=1, url="https://example.com", display_url="example.com", hash=0, title="Example", photo=types.PhotoEmpty(1)
    )
    message = make_message(7, types.PeerUser(2), "https://example.com", media=types.MessageMediaWebPage(webpage=page))
    assert media_info(message) == {"type": "link_preview", "url": "https://example.com", "title": "Example"}


def test_service_message() -> None:
    message = types.MessageService(
        id=8,
        peer_id=types.PeerChat(50),
        date=make_message(1, types.PeerChat(50)).date,
        action=types.MessageActionChatEditTitle(title="Новое название"),
    )
    assert format_message(message)["action"] == "ChatEditTitle"


def test_entities() -> None:
    assert format_entity(make_user(3, "Anna", "anna_k", contact=True)) == {
        "id": 3,
        "type": "user",
        "name": "Anna",
        "username": "anna_k",
        "is_contact": True,
    }
    assert format_entity(make_user(9, "Bot", bot=True))["type"] == "bot"
    assert format_entity(make_user(9, "x", deleted=True))["name"] == "Удалённый аккаунт"
    assert format_entity(make_group(50, "Семья")) == {"id": -50, "type": "group", "name": "Семья", "members": 3}


def test_dialog_preview_for_media() -> None:
    last = make_message(11, types.PeerUser(2), media=voice_media())
    data = format_dialog(make_dialog(make_user(2, "Мама"), unread=4, last=last))
    assert data["name"] == "Мама"
    assert data["unread"] == 4
    assert data["last_message"] == "[voice]"
