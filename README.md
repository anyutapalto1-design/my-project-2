# Telegram MCP

MCP-сервер, через который Claude работает с вашим личным аккаунтом Telegram. Основан на библиотеке
[Telethon](https://github.com/LonamiWebs/Telethon): подключение идёт от имени пользователя, а не бота, поэтому
Claude видит те же чаты, что и вы.

Возможности:

- **Чтение:** список диалогов с непрочитанными, история сообщений, поиск по одному чату или по всем сразу,
  информация о чатах, пользователях и участниках групп. Чтение **не** помечает сообщения прочитанными.
- **Сообщения:** отправка, ответ, редактирование, удаление, пересылка, закрепление, отметка «прочитано».
- **Группы и каналы:** создание, добавление и удаление участников, назначение админов, переименование,
  ссылки-приглашения, вход и выход.
- **Медиа:** скачивание фото, видео, документов; отправка файлов.
- **Контакты:** список, поиск, добавление, удаление, блокировка.
- **Голосовые:** отправка и расшифровка в текст (встроенной расшифровкой Telegram или локально через Whisper).

## Безопасность

- Строка сессии (`TELEGRAM_SESSION_STRING`) даёт **полный доступ к аккаунту**: не публикуйте её и не
  пересылайте никому, в том числе в чат с Claude. Она хранится в `.env`, который не попадает в git.
  Отозвать доступ можно в Telegram: «Настройки → Устройства» → сессия «Telegram MCP».
- Если нужно только читать переписку, включите `TELEGRAM_READ_ONLY=true`: инструменты отправки, удаления
  и управления группами и контактами не будут подключены вовсе.
- Тексты сообщений пишут другие люди. Сервер просит Claude считать их данными, а не командами, но всё равно
  проверяйте, что Claude собирается отправить или удалить: клиенты Claude спрашивают разрешение перед вызовом
  инструмента.
- Telegram разрешает такие клиенты через официальный API, но массовые рассылки и спам приводят к блокировке.

## Установка

Нужен Python 3.10+ и [uv](https://docs.astral.sh/uv/) (или обычный `pip`).

1. Получите **API ID** и **API hash** на [my.telegram.org/apps](https://my.telegram.org/apps)
   (раздел «API development tools», название приложения любое).
2. Скачайте проект и установите зависимости:
   ```bash
   git clone https://github.com/anyutapalto1-design/my-project-2.git
   cd my-project-2
   uv sync
   ```
3. Войдите в аккаунт (один раз):
   ```bash
   uv run python -m telegram_mcp.login
   ```
   Скрипт спросит API ID, API hash, номер телефона, код из Telegram и пароль двухэтапной аутентификации,
   если он включён, и сохранит всё в `.env`. Флаг `--print` выводит данные в терминал вместо записи в файл.

## Подключение к Claude

**Claude Code.** Запустите `claude` в папке проекта: сервер описан в `.mcp.json` и подключится сам
(Claude Code один раз спросит подтверждение). Чтобы сервер был доступен из любой папки:

```bash
claude mcp add --scope user telegram -- uv run --quiet --directory /полный/путь/к/my-project-2 python -m telegram_mcp
```

**Claude Desktop.** Добавьте в `claude_desktop_config.json` (меню «Settings → Developer → Edit Config») и
перезапустите приложение:

```json
{
  "mcpServers": {
    "telegram": {
      "command": "uv",
      "args": ["run", "--quiet", "--directory", "/полный/путь/к/my-project-2", "python", "-m", "telegram_mcp"]
    }
  }
}
```

Если `uv` не находится, укажите полный путь к нему (`which uv` на macOS/Linux, `where uv` на Windows).

После подключения можно просто писать: «что мне писала мама вчера?», «покажи непрочитанные»,
«расшифруй последнее голосовое от Ани», «найди, где обсуждали отпуск».

> Облачные сессии Claude Code (claude.ai/code) работают через HTTPS-прокси, а Telegram использует собственный
> протокол MTProto поверх TCP, поэтому там сервер не может подключиться к Telegram. Запускайте его на своём
> компьютере.

## Инструменты

Чат или пользователя можно указывать по id, `@username`, телефону `+7…`, ссылке `t.me/…`, `me`
(«Избранное») или по имени, как он называется у вас в списке чатов. Если под имя подходит несколько чатов,
сервер вернёт варианты с id.

| Группа | Инструменты |
| --- | --- |
| Аккаунт и чаты | `get_me`, `list_chats`, `get_chat`, `get_participants` |
| Чтение | `get_messages`, `search_messages` |
| Сообщения | `send_message`, `edit_message`, `delete_messages`, `forward_messages`, `pin_message`, `unpin_message`, `mark_as_read` |
| Медиа | `download_media`, `send_file` |
| Голосовые | `transcribe_voice`, `send_voice` |
| Группы | `create_group`, `add_members`, `remove_member`, `set_admin`, `rename_chat`, `get_invite_link`, `join_chat`, `leave_chat` |
| Контакты | `list_contacts`, `search_contacts`, `add_contact`, `delete_contact`, `block_user`, `unblock_user` |

В режиме `TELEGRAM_READ_ONLY=true` остаются только `get_me`, `list_chats`, `get_chat`, `get_participants`,
`get_messages`, `search_messages`, `download_media`, `transcribe_voice`, `list_contacts`, `search_contacts`.

### Расшифровка голосовых

`transcribe_voice` работает с голосовыми, «кружочками» и аудио:

- `telegram` — встроенная расшифровка Telegram. Нужен Telegram Premium (без него Telegram даёт лишь несколько
  бесплатных попыток).
- `whisper` — локально через [faster-whisper](https://github.com/SYSTRAN/faster-whisper), без Premium и без
  отправки аудио куда-либо. Установка: `uv sync --extra whisper`. При первом запуске скачивается модель
  (`WHISPER_MODEL`, по умолчанию `small`, ~500 МБ).
- `auto` (по умолчанию) — сначала Telegram, при ошибке Whisper, если он установлен.

## Настройки

Все параметры задаются в `.env` (образец — `.env.example`) или переменными окружения.

| Переменная | Назначение |
| --- | --- |
| `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` | Данные приложения с my.telegram.org |
| `TELEGRAM_SESSION_STRING` | Строка сессии, создаётся `python -m telegram_mcp.login` |
| `TELEGRAM_READ_ONLY` | `true` — только чтение |
| `TELEGRAM_DOWNLOAD_DIR` | Папка для скачанных файлов, по умолчанию `~/Downloads/telegram-mcp` |
| `TELEGRAM_TRANSCRIPTION` | `auto`, `telegram` или `whisper` |
| `WHISPER_MODEL` | Модель faster-whisper: `tiny`, `base`, `small`, `medium`, `large-v3` |

## Разработка

```bash
uv sync --extra dev
uv run pytest
```

Тесты используют имитацию клиента Telegram и не требуют аккаунта.
