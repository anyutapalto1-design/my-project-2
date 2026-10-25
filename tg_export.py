#!/usr/bin/env python3
"""Выгрузка диалогов из Telegram через ваш собственный аккаунт (Telethon).

Запускайте на своем компьютере. Ключи api_id и api_hash выдаются на
https://my.telegram.org -> API development tools.

Результат — JSON в том же формате, что и экспорт Telegram Desktop,
его читает analyze.py.
"""

import argparse
import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, MessageService, User
from telethon.utils import get_display_name

# Файл tg_export.session дает полный доступ к аккаунту: никому его не передавайте
SESSION = "tg_export"


def chat_type(entity):
    if isinstance(entity, User):
        return "bot_chat" if entity.bot else "personal_chat"
    if isinstance(entity, Chat):
        return "private_group"
    if isinstance(entity, Channel):
        return "supergroup" if entity.megagroup else "channel"
    return "unknown"


def media_type(msg):
    # Порядок важен: стикеры, голосовые и гифки тоже являются документами
    if msg.sticker:
        return "sticker"
    if msg.voice:
        return "voice_message"
    if msg.video_note:
        return "video_message"
    if msg.gif:
        return "animation"
    if msg.photo:
        return "photo"
    if msg.video:
        return "video_file"
    if msg.audio:
        return "audio_file"
    if msg.document:
        return "file"
    return None


def local_iso(dt):
    return dt.astimezone().replace(tzinfo=None).isoformat(timespec="seconds")


def to_record(msg):
    if isinstance(msg, MessageService):
        return {
            "id": msg.id,
            "type": "service",
            "date": local_iso(msg.date),
            "action": type(msg.action).__name__,
        }
    record = {
        "id": msg.id,
        "type": "message",
        "date": local_iso(msg.date),
        "from": get_display_name(msg.sender) if msg.sender else None,
        "from_id": msg.sender_id,
        "text": msg.message or "",
    }
    kind = media_type(msg)
    if kind:
        record["media_type"] = kind
    if msg.reply_to_msg_id:
        record["reply_to_message_id"] = msg.reply_to_msg_id
    if msg.fwd_from:
        record["forwarded_from"] = msg.fwd_from.from_name or "unknown"
    return record


def safe_name(name):
    return re.sub(r"[^\w\-]+", "_", name or "chat").strip("_")[:60] or "chat"


def pick(dialogs, query):
    if re.fullmatch(r"-?\d+", query):
        return [d for d in dialogs if d.id == int(query)]
    q = query.lower()
    exact = [d for d in dialogs if (d.name or "").lower() == q]
    return exact or [d for d in dialogs if q in (d.name or "").lower()]


async def export(client, dialog, args):
    records = []
    async for msg in client.iter_messages(dialog.entity, limit=args.limit):
        if args.since and msg.date < args.since:
            break
        records.append(to_record(msg))
    records.sort(key=lambda r: r["id"])

    data = {
        "name": dialog.name,
        "type": chat_type(dialog.entity),
        "id": dialog.id,
        "messages": records,
    }
    path = args.out / f"{safe_name(dialog.name)}_{abs(dialog.id)}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{dialog.name}: {len(records)} сообщений -> {path}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="показать диалоги и их id")
    parser.add_argument("--chat", action="append", default=[], help="id или часть названия диалога (можно несколько раз)")
    parser.add_argument("--personal", action="store_true", help="выгрузить все личные переписки (без ботов)")
    parser.add_argument("--dialogs", type=int, default=200, help="сколько последних диалогов просматривать (по умолчанию 200)")
    parser.add_argument("--limit", type=int, default=None, help="максимум сообщений на диалог, самые свежие (по умолчанию все)")
    parser.add_argument("--since", type=lambda s: datetime.fromisoformat(s).astimezone(), help="только сообщения начиная с даты, например 2025-01-01")
    parser.add_argument("--out", type=Path, default=Path("exports"), help="папка для результата (по умолчанию exports/)")
    return parser.parse_args()


async def main():
    args = parse_args()
    if not (args.list or args.chat or args.personal):
        raise SystemExit("Укажите --list, --chat или --personal (подробнее: --help)")

    api_id = os.environ.get("TG_API_ID") or input("api_id: ")
    api_hash = os.environ.get("TG_API_HASH") or input("api_hash: ")

    # При первом запуске Telethon спросит номер телефона и код из Telegram
    async with TelegramClient(SESSION, int(api_id), api_hash) as client:
        dialogs = await client.get_dialogs(limit=args.dialogs)

        if args.list:
            for d in dialogs:
                print(f"{d.id:>15}  {chat_type(d.entity):<14} {d.name}")
            return

        selected = []
        for query in args.chat:
            found = pick(dialogs, query)
            if len(found) == 1:
                selected.append(found[0])
            elif not found:
                print(f"Не найден диалог: {query}")
            else:
                names = ", ".join(f"{d.name} ({d.id})" for d in found)
                print(f"Под «{query}» подходит несколько диалогов, укажите id: {names}")
        if args.personal:
            selected += [
                d for d in dialogs
                if chat_type(d.entity) == "personal_chat" and not d.entity.is_self
            ]

        args.out.mkdir(parents=True, exist_ok=True)
        seen = set()
        for dialog in selected:
            if dialog.id not in seen:
                seen.add(dialog.id)
                await export(client, dialog, args)


if __name__ == "__main__":
    asyncio.run(main())
