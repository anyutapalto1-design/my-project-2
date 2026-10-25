import pytest

from telegram_mcp.connection import ChatNotFoundError, NotConfiguredError, TelegramConnection, make_client
from telegram_mcp.config import Settings


async def test_resolve_by_display_name(connection, people) -> None:
    assert await connection.resolve("мама") is people["mom"]
    assert await connection.resolve("Семья") is people["family"]


async def test_exact_name_beats_substring(connection, people) -> None:
    assert await connection.resolve("Anna") is people["anna"]


async def test_ambiguous_name_lists_candidates(connection) -> None:
    with pytest.raises(ChatNotFoundError) as error:
        await connection.resolve("ann")
    assert "Anna (user, id 3)" in str(error.value)
    assert "Anna Work (user, id 4)" in str(error.value)


async def test_bare_word_prefers_own_dialog_over_public_username(connection, fake_client, people) -> None:
    fake_client.public["anna"] = "a stranger owning @anna"
    assert await connection.resolve("Anna") is people["anna"]
    assert await connection.resolve("@anna") == "a stranger owning @anna"


async def test_resolve_id_loads_dialogs_when_not_cached(connection, people) -> None:
    assert await connection.resolve("-50") is people["family"]
    assert await connection.resolve(2) is people["mom"]
    with pytest.raises(ChatNotFoundError):
        await connection.resolve(777)


async def test_resolve_self_and_unknown(connection, people) -> None:
    assert await connection.resolve("me") is people["me"]
    with pytest.raises(ChatNotFoundError):
        await connection.resolve("Нет такого чата")


async def test_unauthorized_session_is_reported(connection, fake_client) -> None:
    fake_client.authorized = False
    with pytest.raises(NotConfiguredError):
        await connection.client()
    assert not fake_client.connected


def test_missing_credentials() -> None:
    with pytest.raises(NotConfiguredError, match="TELEGRAM_API_ID"):
        make_client(Settings.from_env({}))
    with pytest.raises(NotConfiguredError, match="login"):
        make_client(Settings.from_env({"TELEGRAM_API_ID": "1", "TELEGRAM_API_HASH": "x"}))


async def test_connect_hooks_run_once(settings, fake_client) -> None:
    seen = []
    connection = TelegramConnection(settings, client_factory=lambda _: fake_client)
    connection.on_connect(seen.append)
    await connection.client()
    await connection.client()
    assert seen == [fake_client]
