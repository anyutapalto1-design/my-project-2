"""One-step setup: log into Telegram if needed and register the server with Claude.

Run by install.sh, or by hand:  python -m telegram_mcp.install
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import Settings, load_env_file
from .login import login

SERVER_NAME = "telegram"


def claude_desktop_config_path() -> Path | None:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    return None


def server_entry() -> dict[str, list[str] | str]:
    # The project's own interpreter: the Claude apps do not inherit the shell PATH.
    return {"command": sys.executable, "args": ["-m", "telegram_mcp"]}


def register_claude_desktop(config_path: Path) -> bool:
    """Add the server to Claude Desktop's config, keeping everything else in it."""
    config: dict = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            print(f"Не удалось прочитать {config_path}: файл повреждён, Claude Desktop не настроен.")
            return False
        shutil.copy2(config_path, config_path.with_name(config_path.name + ".bak"))
    config.setdefault("mcpServers", {})[SERVER_NAME] = server_entry()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def register_claude_code(claude: str) -> bool:
    entry = server_entry()
    subprocess.run([claude, "mcp", "remove", "--scope", "user", SERVER_NAME], capture_output=True)
    added = subprocess.run(
        [claude, "mcp", "add", "--scope", "user", SERVER_NAME, "--", entry["command"], *entry["args"]],
        capture_output=True,
        text=True,
    )
    return added.returncode == 0


def main() -> None:
    load_env_file()
    if not Settings.from_env().session_string:
        asyncio.run(login(print_only=False))
    else:
        print("Вход в Telegram уже выполнен.")

    connected = []
    desktop_config = claude_desktop_config_path()
    if desktop_config and register_claude_desktop(desktop_config):
        connected.append("Claude Desktop")
    claude = shutil.which("claude")
    if claude and register_claude_code(claude):
        connected.append("Claude Code")

    if not connected:
        entry = server_entry()
        print("\nНе нашёл приложений Claude. Добавьте MCP-сервер вручную:")
        print(f"  команда: {entry['command']} {' '.join(entry['args'])}")
        return

    print(f"\nTelegram подключён к: {', '.join(connected)}.")
    if "Claude Desktop" in connected:
        print("Полностью закройте Claude (⌘Q) и откройте снова.")
    print("Потом напишите Claude, например: «Покажи непрочитанные в Telegram».")


if __name__ == "__main__":
    main()
