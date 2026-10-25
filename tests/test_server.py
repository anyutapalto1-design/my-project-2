import json
import sys
from pathlib import Path

import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from mcp.server.mcpserver.exceptions import ToolError

from telegram_mcp.config import Settings
from telegram_mcp.server import _invite_hash, build_server

READ_TOOLS = {
    "get_me",
    "list_chats",
    "get_chat",
    "get_messages",
    "search_messages",
    "get_participants",
    "download_media",
    "transcribe_voice",
    "list_contacts",
    "search_contacts",
}


async def call(server, name, **arguments):
    result = await server.call_tool(name, arguments)
    assert not result.is_error, result.content
    return result.structured_content


async def test_read_only_mode_registers_only_read_tools(settings, connection) -> None:
    full = {tool.name for tool in await build_server(settings, connection).list_tools()}
    read_only = Settings.from_env({"TELEGRAM_READ_ONLY": "true"})
    limited = {tool.name for tool in await build_server(read_only, connection).list_tools()}
    assert limited == READ_TOOLS
    assert {"send_message", "delete_messages", "create_group", "add_contact"} <= full - limited


async def test_list_chats_filters_unread(settings, connection) -> None:
    result = await call(build_server(settings, connection), "list_chats", unread_only=True)
    assert [chat["name"] for chat in result["chats"]] == ["Мама"]
    assert result["chats"][0]["last_message"] == "Позвони, как сможешь"


async def test_get_messages_is_chronological_and_pages_back(settings, connection) -> None:
    server = build_server(settings, connection)
    first = await call(server, "get_messages", chat="Мама", limit=2)
    assert [message["id"] for message in first["messages"]] == [11, 12]
    assert first["messages"][0]["media"]["type"] == "voice"
    assert first["older_offset_id"] == 11

    older = await call(server, "get_messages", chat="Мама", limit=2, offset_id=first["older_offset_id"])
    assert [message["id"] for message in older["messages"]] == [10]
    assert "older_offset_id" not in older


async def test_send_message_goes_to_resolved_chat(settings, connection, fake_client, people) -> None:
    result = await call(build_server(settings, connection), "send_message", chat="мама", text="Уже звоню", reply_to=12)
    entity, text, kwargs = fake_client.sent[0]
    assert entity is people["mom"]
    assert text == "Уже звоню"
    assert kwargs["reply_to"] == 12
    assert result["sent"]["text"] == "Уже звоню"


async def test_errors_reach_the_model_readably(settings, connection) -> None:
    # ToolError (unlike other exceptions) keeps its message when sent to the client.
    with pytest.raises(ToolError, match="несколько чатов"):
        await build_server(settings, connection).call_tool("get_messages", {"chat": "ann"})


async def test_transcribe_rejects_text_messages(settings, connection) -> None:
    with pytest.raises(ToolError, match="не голосовое"):
        await build_server(settings, connection).call_tool("transcribe_voice", {"chat": "Мама", "message_id": 10})


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("https://t.me/+AbCdEf123", "AbCdEf123"),
        ("t.me/joinchat/XyZ", "XyZ"),
        ("@durov", None),
        ("https://t.me/durov", None),
    ],
)
def test_invite_hash(link, expected) -> None:
    assert _invite_hash(link) == expected


async def test_stdio_server_starts_without_credentials(tmp_path) -> None:
    """The real entry point speaks MCP over stdio and explains what is missing."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "telegram_mcp"],
        cwd=str(Path(__file__).resolve().parent.parent),
        env={"TELEGRAM_API_ID": "", "TELEGRAM_API_HASH": "", "TELEGRAM_SESSION_STRING": "", "HOME": str(tmp_path)},
    )
    async with Client(params) as client:
        tools = await client.list_tools()
        assert len(tools.tools) == 31
        result = await client.call_tool("list_chats", {})
        assert result.is_error
        assert "TELEGRAM_API_ID" in json.dumps(result.model_dump(), ensure_ascii=False)
