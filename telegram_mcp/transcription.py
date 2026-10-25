"""Voice message transcription: Telegram's built-in one (Premium) or local Whisper."""

from __future__ import annotations

import asyncio
import importlib.util
import tempfile
import threading
import time
from typing import Any

from telethon import TelegramClient, errors, events, functions
from telethon.tl import types

from .config import Settings

TELEGRAM_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 0.5


class TranscriptionError(RuntimeError):
    pass


def whisper_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


class Transcriber:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # Telegram finishes long transcriptions asynchronously and pushes the
        # text as UpdateTranscribedAudio; finished texts land here by id.
        self._finished: dict[int, str] = {}
        self._whisper_model: Any = None
        self._whisper_lock = threading.Lock()

    def attach(self, client: TelegramClient) -> None:
        client.add_event_handler(self._on_update, events.Raw(types.UpdateTranscribedAudio))

    async def _on_update(self, update: types.UpdateTranscribedAudio) -> None:
        if not update.pending:
            self._finished[update.transcription_id] = update.text

    async def transcribe(self, client: TelegramClient, chat: Any, message: Any, method: str) -> dict[str, Any]:
        if not (message.voice or message.video_note or message.audio):
            raise TranscriptionError(f"Сообщение {message.id} не голосовое и не аудио.")

        if method == "telegram":
            return await self._telegram(client, chat, message)
        if method == "whisper":
            return await self._whisper(client, message)

        try:
            return await self._telegram(client, chat, message)
        except (errors.RPCError, TranscriptionError) as exc:
            if not whisper_available():
                raise TranscriptionError(
                    f"Telegram не смог расшифровать сообщение ({exc}). Встроенная расшифровка требует "
                    "Telegram Premium; для локальной расшифровки установите faster-whisper: "
                    "pip install 'telegram-mcp[whisper]'."
                ) from exc
            result = await self._whisper(client, message)
            result["telegram_error"] = str(exc)
            return result

    async def _telegram(self, client: TelegramClient, chat: Any, message: Any) -> dict[str, Any]:
        request = functions.messages.TranscribeAudioRequest(peer=chat, msg_id=message.id)
        result = await client(request)
        deadline = time.monotonic() + TELEGRAM_TIMEOUT_SECONDS
        text = result.text

        while result.pending:
            finished = self._finished.pop(result.transcription_id, None)
            if finished is not None:
                text = finished
                break
            if time.monotonic() > deadline:
                # A repeated request returns the stored transcription once it is ready.
                result = await client(request)
                if result.pending:
                    raise TranscriptionError("Telegram ещё расшифровывает сообщение, попробуйте позже.")
                text = result.text
                break
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

        return {
            "method": "telegram",
            "text": text,
            "trial_remains": result.trial_remains_num,
        }

    async def _whisper(self, client: TelegramClient, message: Any) -> dict[str, Any]:
        if not whisper_available():
            raise TranscriptionError("Локальная расшифровка недоступна: pip install 'telegram-mcp[whisper]'.")
        with tempfile.TemporaryDirectory(prefix="telegram-mcp-") as tmp:
            path = await client.download_media(message, file=tmp)
            text, language = await asyncio.to_thread(self._run_whisper, path)
        return {"method": "whisper", "text": text, "language": language}

    def _run_whisper(self, path: str) -> tuple[str, str]:
        with self._whisper_lock:
            if self._whisper_model is None:
                from faster_whisper import WhisperModel

                self._whisper_model = WhisperModel(self._settings.whisper_model, device="auto", compute_type="int8")
            segments, info = self._whisper_model.transcribe(path, vad_filter=True)
            text = " ".join(segment.text.strip() for segment in segments).strip()
        return text, info.language
