import json
import sys

from telegram_mcp.install import register_claude_desktop


def test_adds_server_and_keeps_existing_config(tmp_path) -> None:
    config_path = tmp_path / "Claude" / "claude_desktop_config.json"
    config_path.parent.mkdir()
    config_path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}))

    assert register_claude_desktop(config_path)

    config = json.loads(config_path.read_text())
    assert config["theme"] == "dark"
    assert config["mcpServers"]["other"] == {"command": "x"}
    assert config["mcpServers"]["telegram"] == {"command": sys.executable, "args": ["-m", "telegram_mcp"]}
    assert json.loads(config_path.with_name("claude_desktop_config.json.bak").read_text())["theme"] == "dark"


def test_creates_missing_config(tmp_path) -> None:
    config_path = tmp_path / "Claude" / "claude_desktop_config.json"
    assert register_claude_desktop(config_path)
    assert "telegram" in json.loads(config_path.read_text())["mcpServers"]


def test_leaves_broken_config_alone(tmp_path) -> None:
    config_path = tmp_path / "claude_desktop_config.json"
    config_path.write_text("{not json")
    assert not register_claude_desktop(config_path)
    assert config_path.read_text() == "{not json"
