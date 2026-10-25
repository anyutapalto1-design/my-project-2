#!/bin/bash
# Установка Telegram MCP одной командой (macOS):
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/anyutapalto1-design/my-project-2/claude/vibrant-maxwell-kwk8b5/install.sh)"
set -euo pipefail

REPO="anyutapalto1-design/my-project-2"
BRANCH="${TELEGRAM_MCP_BRANCH:-claude/vibrant-maxwell-kwk8b5}"
DIR="${TELEGRAM_MCP_DIR:-$HOME/telegram-mcp}"

export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "==> Устанавливаю uv (менеджер Python)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

echo "==> Скачиваю Telegram MCP в $DIR"
mkdir -p "$DIR"
curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" | tar -xz --strip-components=1 -C "$DIR"
cd "$DIR"

echo "==> Устанавливаю зависимости"
uv sync --quiet

echo
uv run --quiet python -m telegram_mcp.install
