"""Entry point: python -m telegram_mcp (MCP over stdio)."""

from __future__ import annotations

import logging
import sys

from .config import Settings, load_env_file
from .server import build_server


def main() -> None:
    # stdout carries the MCP protocol, so all logs go to stderr.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    load_env_file()
    build_server(Settings.from_env()).run("stdio")


if __name__ == "__main__":
    main()
