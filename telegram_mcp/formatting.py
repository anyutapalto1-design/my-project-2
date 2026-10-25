"""Turn Telethon objects into compact, JSON-friendly dicts for the model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from telethon import utils
from telethon.tl import types


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    """Drop empty fields so every message costs fewer tokens."""
    return {key: value for key, value in data.items() if value not in (None, "", [], {}, False)}


def format_date(value: datetime | None) -> str | None:
    """ISO timestamp in the machine's local timezone (Telegram sends UTC)."""
    if value is None:
        return None
    return value.astimezone().isoformat(timespec="seconds")


def display_name(entity: Any) -> str:
    if entity is None:
        return ""
    if isinstance(entity, types.User) and entity.deleted:
        return "Удалённый аккаунт"
    return utils.get_display_name(entity) or getattr(entity, "username", None) or str(getattr(entity, "id", ""))


def entity_kind(entity: Any) -> str:
    if isinstance(entity, types.User):
        return "bot" if entity.bot else "user"
    if isinstance(entity, (types.Chat, types.ChatForbidden)):
        return "group"
    if isinstance(entity, (types.Channel, types.ChannelForbidden)):
        return "supergroup" if getattr(entity, "megagroup", False) else "channel"
    return "unknown"


def format_entity(entity: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": utils.get_peer_id(entity),
        "type": entity_kind(entity),
        "name": display_name(entity),
        "username": getattr(entity, "username", None),
    }
    if isinstance(entity, types.User):
        data.update(
            phone=entity.phone,
            is_contact=entity.contact,
            is_self=entity.is_self,
            premium=entity.premium,
            status=_user_status(entity.status),
        )
    else:
        data["members"] = getattr(entity, "participants_count", None)
    return _compact(data)


def _user_status(status: Any) -> str | None:
    if isinstance(status, types.UserStatusOnline):
        return "online"
    if isinstance(status, types.UserStatusOffline):
        return f"last seen {format_date(status.was_online)}"
    if isinstance(status, types.UserStatusRecently):
        return "recently"
    if isinstance(status, types.UserStatusLastWeek):
        return "within a week"
    if isinstance(status, types.UserStatusLastMonth):
        return "within a month"
    return None


def format_dialog(dialog: Any) -> dict[str, Any]:
    entity = dialog.entity
    last = dialog.message
    return _compact(
        {
            "id": dialog.id,
            "type": entity_kind(entity),
            "name": dialog.name or display_name(entity),
            "username": getattr(entity, "username", None),
            "unread": dialog.unread_count,
            "mentions": dialog.unread_mentions_count,
            "pinned": dialog.pinned,
            "archived": dialog.archived,
            "muted": _is_muted(dialog),
            "last_message": _preview(last) if last else None,
            "last_date": format_date(last.date) if last else None,
        }
    )


def _is_muted(dialog: Any) -> bool:
    settings = getattr(dialog.dialog, "notify_settings", None)
    mute_until = getattr(settings, "mute_until", None)
    if mute_until is None:
        return False
    return mute_until.timestamp() > datetime.now().timestamp()


def _preview(message: Any, limit: int = 120) -> str:
    text = (getattr(message, "message", None) or "").replace("\n", " ")
    if not text:
        media = media_info(message)
        text = f"[{media['type']}]" if media else ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def media_info(message: Any) -> dict[str, Any] | None:
    if not getattr(message, "media", None):
        return None

    # Link previews also expose .photo/.document, so classify them first.
    if isinstance(message.media, types.MessageMediaWebPage):
        page = message.web_preview
        return _compact(
            {"type": "link_preview", "url": getattr(page, "url", None), "title": getattr(page, "title", None)}
        )

    if message.voice:
        kind = "voice"
    elif message.video_note:
        kind = "video_note"
    elif message.sticker:
        kind = "sticker"
    elif message.gif:
        kind = "gif"
    elif message.audio:
        kind = "audio"
    elif message.video:
        kind = "video"
    elif message.photo:
        kind = "photo"
    elif message.document:
        kind = "document"
    elif message.poll:
        poll = message.poll.poll
        question = getattr(poll.question, "text", poll.question)
        options = [getattr(answer.text, "text", answer.text) for answer in poll.answers]
        return {"type": "poll", "question": question, "options": options}
    elif message.geo:
        return {"type": "location", "lat": message.geo.lat, "long": message.geo.long}
    elif message.contact:
        contact = message.contact
        return _compact(
            {
                "type": "contact",
                "name": f"{contact.first_name} {contact.last_name}".strip(),
                "phone": contact.phone_number,
                "user_id": contact.user_id,
            }
        )
    else:
        return {"type": type(message.media).__name__.removeprefix("MessageMedia").lower()}

    file = message.file
    return _compact(
        {
            "type": kind,
            "file_name": file.name if file else None,
            "mime_type": file.mime_type if file else None,
            "size": file.size if file else None,
            "duration": file.duration if file else None,
            "emoji": file.emoji if file and kind == "sticker" else None,
        }
    )


def _forward_source(message: Any) -> str | None:
    forward = getattr(message, "fwd_from", None)
    if forward is None:
        return None
    if forward.from_name:
        return forward.from_name
    if message.forward is not None:
        sender = message.forward.sender or message.forward.chat
        if sender is not None:
            return display_name(sender)
    if forward.from_id is not None:
        return str(utils.get_peer_id(forward.from_id))
    return "hidden"


def format_message(message: Any) -> dict[str, Any]:
    if isinstance(message, types.MessageService):
        return _compact(
            {
                "id": message.id,
                "date": format_date(message.date),
                "from_id": message.sender_id,
                "from": display_name(message.sender),
                "action": type(message.action).__name__.removeprefix("MessageAction"),
            }
        )

    return _compact(
        {
            "id": message.id,
            "date": format_date(message.date),
            "from_id": message.sender_id,
            "from": display_name(message.sender),
            "out": message.out,
            "text": message.message,
            "reply_to": message.reply_to_msg_id,
            "forwarded_from": _forward_source(message),
            "media": media_info(message),
            "edited": format_date(message.edit_date) if message.edit_date and not message.edit_hide else None,
            "views": message.views,
        }
    )
