#!/usr/bin/env python3
"""Статистика по переписке из экспорта Telegram.

Понимает JSON из Telegram Desktop (один чат или полный экспорт result.json)
и файлы, которые создает tg_export.py. Работает без сторонних библиотек.
"""

import argparse
import json
import re
from collections import Counter
from datetime import timedelta, datetime
from pathlib import Path
from statistics import median

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MEDIA_LABELS = {
    "sticker": "стикер",
    "voice_message": "голосовое",
    "video_message": "кружок",
    "animation": "гифка",
    "video_file": "видео",
    "audio_file": "аудио",
    "photo": "фото",
    "file": "файл",
}
STOPWORDS = set("""
и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только
ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни
быть был него до вас нибудь опять уж вам ведь там потом себя ничего ей может они тут где
есть надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж
тогда кто этот того потому этого какой совсем ним здесь этом один почти мой тем чтобы нее
сейчас были куда зачем всех никогда можно при наконец два об другой хоть после над больше
тот через эти нас про всего них какая много разве три эту моя впрочем хорошо свою этой
перед иногда лучше чуть том нельзя такой им более всегда конечно всю между это как-то
просто очень вообще тоже типа щас сегодня завтра вчера тебе меня мне нам вам вот так
ага угу ок окей ладно давай пока привет спасибо пожалуйста буду будешь есть было
the and you that for are with this have not but what your just was can all
""".split())


def load_chats(paths):
    chats = []
    for path in map(Path, paths):
        files = sorted(path.glob("**/*.json")) if path.is_dir() else [path]
        for file in files:
            with open(file, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                continue
            if "chats" in data:
                chats.extend(data["chats"].get("list", []))
                chats.extend(data.get("left_chats", {}).get("list", []))
            elif "messages" in data:
                chats.append(data)
    return chats


def message_text(msg):
    text = msg.get("text", "")
    if isinstance(text, list):
        text = "".join(p if isinstance(p, str) else p.get("text", "") for p in text)
    return text


def media_kind(msg):
    if msg.get("media_type"):
        return msg["media_type"]
    if "photo" in msg:
        return "photo"
    if "file" in msg:
        return "file"
    return None


def parse_messages(chat):
    result = []
    for msg in chat.get("messages", []):
        if msg.get("type") != "message":
            continue
        result.append({
            "date": datetime.fromisoformat(msg["date"]),
            "author": msg.get("from") or "Удаленный аккаунт",
            "text": message_text(msg),
            "media": media_kind(msg),
            "forwarded": bool(msg.get("forwarded_from")),
        })
    result.sort(key=lambda m: m["date"])
    return result


def split_sessions(messages, gap):
    sessions = []
    for m in messages:
        if sessions and m["date"] - sessions[-1][-1]["date"] < gap:
            sessions[-1].append(m)
        else:
            sessions.append([m])
    return sessions


def fmt_duration(delta):
    minutes = delta.total_seconds() / 60
    if minutes < 1:
        return "<1 мин"
    if minutes < 60:
        return f"{minutes:.0f} мин"
    if minutes < 48 * 60:
        return f"{minutes / 60:.1f} ч"
    return f"{minutes / 60 / 24:.0f} дн"


def bars(counter, keys, labels=None, width=30):
    peak = max((counter[k] for k in keys), default=0) or 1
    lines = []
    for i, key in enumerate(keys):
        label = labels[i] if labels else str(key)
        lines.append(f"{label:>7} {'█' * round(counter[key] / peak * width):<{width}} {counter[key]}")
    return ["```", *lines, "```"]


def top_words(messages, n):
    words = Counter()
    for m in messages:
        text = re.sub(r"\S+://\S+|www\.\S+", " ", m["text"].lower().replace("ё", "е"))
        for word in re.findall(r"[a-zа-я]+", text):
            if len(word) >= 3 and word not in STOPWORDS:
                words[word] += 1
    return words.most_common(n)


def chat_report(chat, messages, args):
    name = chat.get("name") or "(без названия)"
    first, last = messages[0]["date"], messages[-1]["date"]
    span_days = (last.date() - first.date()).days + 1
    active_days = len({m["date"].date() for m in messages})
    sessions = split_sessions(messages, timedelta(hours=args.gap))

    authors = Counter(m["author"] for m in messages)
    starts = Counter(s[0]["author"] for s in sessions)
    replies = {}
    for session in sessions:
        for prev, cur in zip(session, session[1:]):
            if cur["author"] != prev["author"]:
                replies.setdefault(cur["author"], []).append(cur["date"] - prev["date"])

    silence = max(
        ((b["date"] - a["date"], a["date"]) for a, b in zip(messages, messages[1:])),
        default=None,
    )

    lines = [
        f"## {name}",
        "",
        f"- Период: {first:%d.%m.%Y} — {last:%d.%m.%Y}",
        f"- Сообщений: {len(messages)}, дней с перепиской: {active_days} из {span_days}",
        f"- Разговоров (пауза между ними от {args.gap:g} ч): {len(sessions)}",
    ]
    if silence:
        lines.append(f"- Самая долгая пауза: {fmt_duration(silence[0])}, после {silence[1]:%d.%m.%Y}")

    lines += [
        "",
        "### Участники",
        "",
        "| Участник | Сообщений | Доля | Ср. длина текста | Начинает разговор | Медиана ответа | Медиа |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for author, count in authors.most_common(args.people):
        own = [m for m in messages if m["author"] == author]
        texts = [len(m["text"]) for m in own if m["text"]]
        media = Counter(MEDIA_LABELS.get(m["media"], m["media"]) for m in own if m["media"])
        media_str = ", ".join(f"{k} {v}" for k, v in media.most_common(4)) or "—"
        reply = fmt_duration(median(replies[author])) if author in replies else "—"
        avg_len = f"{sum(texts) / len(texts):.0f}" if texts else "—"
        lines.append(
            f"| {author.replace('|', '/')} | {count} | {count / len(messages):.0%} | {avg_len} "
            f"| {starts[author]} | {reply} | {media_str} |"
        )

    hours = Counter(m["date"].hour for m in messages)
    weekdays = Counter(m["date"].weekday() for m in messages)
    months = Counter(m["date"].strftime("%Y-%m") for m in messages)
    lines += ["", "### Время суток", "", *bars(hours, range(24), [f"{h:02d}:00" for h in range(24)])]
    lines += ["", "### Дни недели", "", *bars(weekdays, range(7), WEEKDAYS)]
    lines += ["", "### По месяцам", "", *bars(months, sorted(months))]

    lines += ["", "### Частые слова", ""]
    for author, _ in authors.most_common(min(args.people, 5)):
        words = top_words((m for m in messages if m["author"] == author), args.words)
        lines.append(f"- **{author}**: " + (", ".join(f"{w} ({c})" for w, c in words) or "—"))
    return lines


def transcript_lines(messages):
    for m in messages:
        tags = []
        if m["forwarded"]:
            tags.append("[переслано]")
        if m["media"]:
            tags.append(f"[{MEDIA_LABELS.get(m['media'], m['media'])}]")
        body = " ".join([*tags, m["text"].replace("\n", "\n    ")]).strip()
        yield f"{m['date']:%Y-%m-%d %H:%M} {m['author']}: {body}"


def safe_name(name):
    return re.sub(r"[^\w\-]+", "_", name or "chat").strip("_")[:60] or "chat"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help="JSON-файлы экспорта или папки с ними")
    parser.add_argument("--chat", action="append", default=[], help="часть названия чата (можно несколько раз)")
    parser.add_argument("--top", type=int, default=10, help="подробный разбор для N самых активных чатов (по умолчанию 10)")
    parser.add_argument("--gap", type=float, default=6, help="пауза в часах, после которой начинается новый разговор (по умолчанию 6)")
    parser.add_argument("--people", type=int, default=15, help="сколько участников показывать (по умолчанию 15)")
    parser.add_argument("--words", type=int, default=15, help="сколько частых слов показывать (по умолчанию 15)")
    parser.add_argument("-o", "--output", type=Path, help="сохранить отчет в файл вместо вывода на экран")
    parser.add_argument("--transcript", type=Path, help="папка, куда сохранить переписки в виде компактного текста")
    return parser.parse_args()


def main():
    args = parse_args()
    chats = []
    for chat in load_chats(args.paths):
        name = (chat.get("name") or "").lower()
        if args.chat and not any(q.lower() in name for q in args.chat):
            continue
        messages = parse_messages(chat)
        if messages:
            chats.append((chat, messages))
    if not chats:
        raise SystemExit("Не нашлось ни одного чата с сообщениями")
    chats.sort(key=lambda c: len(c[1]), reverse=True)

    lines = ["# Анализ переписки Telegram", ""]
    if len(chats) > 1:
        lines += ["| Чат | Тип | Сообщений | Последнее |", "|---|---|---:|---|"]
        for chat, messages in chats:
            lines.append(
                f"| {(chat.get('name') or '(без названия)').replace('|', '/')} | {chat.get('type', '')} "
                f"| {len(messages)} | {messages[-1]['date']:%d.%m.%Y} |"
            )
        lines.append("")
    for chat, messages in chats[:args.top]:
        lines += chat_report(chat, messages, args) + [""]

    report = "\n".join(lines)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"Отчет сохранен: {args.output}")
    else:
        print(report)

    if args.transcript:
        args.transcript.mkdir(parents=True, exist_ok=True)
        for chat, messages in chats[:args.top]:
            path = args.transcript / f"{safe_name(chat.get('name'))}.txt"
            path.write_text("\n".join(transcript_lines(messages)) + "\n", encoding="utf-8")
            print(f"Текст переписки: {path}")


if __name__ == "__main__":
    main()
