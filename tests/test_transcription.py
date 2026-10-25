import asyncio

import pytest
from telethon import errors
from telethon.tl import types

from telegram_mcp import transcription
from telegram_mcp.transcription import Transcriber, TranscriptionError

from .conftest import make_message, voice_media

VOICE = make_message(11, types.PeerUser(2), media=voice_media())


class TranscribingClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.handlers = []

    def add_event_handler(self, callback, event):
        self.handlers.append(callback)

    async def __call__(self, request):
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


async def test_waits_for_pending_transcription_update(settings, monkeypatch) -> None:
    monkeypatch.setattr(transcription, "POLL_INTERVAL_SECONDS", 0.01)
    client = TranscribingClient(types.messages.TranscribedAudio(transcription_id=5, text="", pending=True))
    transcriber = Transcriber(settings)
    transcriber.attach(client)

    async def deliver_update():
        await asyncio.sleep(0.05)
        await client.handlers[0](
            types.UpdateTranscribedAudio(peer=types.PeerUser(2), msg_id=11, transcription_id=5, text="Перезвони мне")
        )

    task = asyncio.create_task(deliver_update())
    result = await transcriber.transcribe(client, "chat", VOICE, "telegram")
    await task
    assert result == {"method": "telegram", "text": "Перезвони мне", "trial_remains": None}


async def test_auto_explains_premium_when_whisper_missing(settings, monkeypatch) -> None:
    monkeypatch.setattr(transcription, "whisper_available", lambda: False)
    client = TranscribingClient(errors.PremiumAccountRequiredError(request=None))
    with pytest.raises(TranscriptionError, match="Premium"):
        await Transcriber(settings).transcribe(client, "chat", VOICE, "auto")


async def test_auto_falls_back_to_whisper(settings, monkeypatch) -> None:
    monkeypatch.setattr(transcription, "whisper_available", lambda: True)

    async def fake_whisper(self, client, message):
        return {"method": "whisper", "text": "локально", "language": "ru"}

    monkeypatch.setattr(Transcriber, "_whisper", fake_whisper)
    client = TranscribingClient(errors.PremiumAccountRequiredError(request=None))
    result = await Transcriber(settings).transcribe(client, "chat", VOICE, "auto")
    assert result["text"] == "локально"
    assert "premium account is required" in result["telegram_error"]
