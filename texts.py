"""Тексты по умолчанию (ru/en), вынесенные из ``app/locales/*.yaml``.

Библиотека не навязывает i18n-движок: ``TextProvider`` — это любой объект
с методами ``get(lang, key, **kwargs)``, ``table(lang, key)`` и
``status_title(lang, status)``. Можно подсунуть свой провайдер (например,
обёртку над yaml-файлами хоста) или просто перекрыть отдельные строки
через ``RoomsConfig.text_overrides``.

Значения с плейсхолдерами ``{name}``, ``{lo}`` и т.п. подставляются через
``str.format`` — сохраняйте фигурные скобки при переводе.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

_MISSING = object()

#: Код ошибки бэкенда → ключ текста. Хост может переопределить через
#: ``text_overrides``, подставив свой текст под тем же ключом.
ERROR_TEXT_KEYS: dict[str, str] = {
    "room_full": "LOBBY_ROOM_FULL",
    "room_not_found": "LOBBY_ROOM_NOT_FOUND",
    "invalid_room_state": "LOBBY_INVALID_STATE",
    "already_in_room": "LOBBY_ALREADY_IN_ROOM",
    "room_access_denied": "LOBBY_WRONG_PASSWORD",
    "forbidden": "LOBBY_ONLY_OWNER",
    "player_not_found": "LOBBY_PLAYER_NOT_FOUND",
    "self_kick": "LOBBY_SELF_KICK",
    "blacklisted": "ERR_BLACKLISTED",
    "not_supported": "GENERIC_ERROR",
    "connection_error": "GENERIC_ERROR",
    "unknown": "GENERIC_ERROR",
}

#: Событие ``notify_room_changed`` → ключ уведомления участникам.
EVENT_TEXT_KEYS: dict[str, str] = {
    "player_joined": "EVENT_PLAYER_JOINED",
    "player_left": "EVENT_PLAYER_LEFT",
    "player_kicked": "EVENT_PLAYER_KICKED",
    "owner_changed": "EVENT_OWNER_CHANGED",
    "room_deleted": "EVENT_ROOM_DELETED",
    "blacklist_changed": "EVENT_BLACKLIST_CHANGED",
    "settings_updated": "EVENT_SETTINGS_UPDATED",
}

_RU: dict[str, Any] = {
    # --- кнопки / меню ---
    "CANCEL": "❌ Отмена",
    "BACK": "⬅️ Назад",
    "PREV": "◀️",
    "NEXT": "▶️",
    "PAGINATION_PAGE": "📄 {cur}/{total}",
    "JOIN_BY_CODE": "По коду",
    "JOIN_LIST": "📋 Список комнат",
    "MAIN_CREATE": "🎲 Создать комнату",
    "MAIN_JOIN": "🔗 Найти комнату",
    "MAIN_ROOMS": "📋 Список комнат",
    "SETTINGS": "⚙️ Настройки",
    "LOBBY_LEAVE": "🚪 Выйти",
    "LOBBY_BLACKLIST": "🚫 Чёрный список",
    "BLACKLIST_ADD": "➕ Добавить",
    "BLACKLIST_REMOVE": "➖ Убрать",
    "KICK_EMPTY": "Нет игроков",
    "PARDON_EMPTY": "Список пуст",
    "LEAVE_GO": "🚪 Я ухожу",
    "LEAVE_STAY": "🙋 Я остаюсь",
    "PRIVACY_PRIVATE": "🔒 Приватная",
    "PRIVACY_PUBLIC": "🌐 Открытая",
    "MENU_TITLE": "<b>Главное меню</b>\nВыберите действие:",
    "PLACEHOLDER": "Эта функция будет доступна в следующих обновлениях.",
    # --- общее ---
    "GENERIC_ERROR": "Упс, что-то пошло не так.",
    "ERR_BLACKLISTED": "🚫 Вы находитесь в чёрном списке этой комнаты. Войти нельзя.",
    "STATUS_TITLES": {
        "waiting": "Ожидание участников",
        "starting": "Подготовка",
        "playing": "Идёт игра",
        "finished": "Завершена",
    },
    # --- главное сообщение комнаты ---
    "ROOM_INFO_TITLE": "<b>🎲 {name}</b>",
    "ROOM_INFO_CODE": "Код комнаты: <code>{code}</code>",
    "ROOM_INFO_PRIVACY_STATUS": "{privacy} | {status}",
    "ROOM_INFO_PLAYERS": "<b>Участники ({cur}/{max}):</b>",
    "ROOM_INFO_MEMBER": "• <code>{name}</code>{suffix}",
    "ROOM_INFO_SETTINGS": "<b>Настройки:</b>",
    "ROOM_INFO_SETTING_LINE": "• {field}: {value}",
    "ROOM_INFO_SETTINGS_EMPTY": "<i>Настроек нет</i>",
    "ROOM_INFO_OWNER_MARK": "👑",
    "ROOM_INFO_BOT_MARK": "🤖",
    "ROOM_INFO_LEFT_MARK": "🚪",
    # --- создание комнаты ---
    "CREATE_NAME_PROMPT": "Введи название комнаты:",
    "CREATE_NAME_ERROR": "Название должно быть от 1 до 60 символов. Попробуйте ещё раз:",
    "CREATE_PRIVACY_PROMPT": "Комната приватная?",
    "CREATE_PASSWORD_PROMPT": "Введи пароль для комнаты:",
    "CREATE_PASSWORD_ERROR": "Пароль должен быть от 1 до 64 символов. Попробуйте ещё раз:",
    "CREATE_MAX_PLAYERS_PROMPT": "Максимум участников ({lo}–{hi}):",
    "CREATE_NUMBER_NAN": "Введите число от {lo} до {hi}:",
    "CREATE_NUMBER_RANGE": "Число должно быть от {lo} до {hi}:",
    "CREATE_ALREADY_IN_ROOM": "Нельзя создать комнату, пока вы находитесь в другой комнате.",
    # --- вход / список комнат ---
    "JOIN_METHOD_PROMPT": "Как хочешь присоединиться?",
    "JOIN_CODE_PROMPT": "Введите код комнаты:",
    "JOIN_CODE_EMPTY": "Код не может быть пустым. Попробуйте ещё раз:",
    "JOIN_PRIVATE_NEED_PASSWORD": "🔒 Эта комната защищена паролем. Введи его, чтобы присоединиться:",
    "JOIN_ROOMS_EMPTY": "Сейчас нет открытых комнат в ожидании.",
    "JOIN_ROOMS_EMPTY_PAGE": "<b>📋 Открытые комнаты</b> — страница {cur}/{total}\n\nСписок пуст.",
    "JOIN_ROOMS_TITLE": "<b>📋 Открытые комнаты</b> — страница {cur}/{total}\n\nВыбери комнату для входа:",
    "JOIN_PAGE_PROMPT": "Введи номер страницы (число):",
    "JOIN_PAGE_NAN": "Введи целое число страницы:",
    "JOIN_PAGE_EMPTY": "Страница {page} пуста. Введи число от 1 до {total}:",
    "JOIN_NO_ROOMS": "Сейчас нет открытых комнат.",
    "ROOM_LIST_LABEL": "{owner} - {name} - ({cur}/{max})",
    # --- лобби / ошибки входа ---
    "LOBBY_ROOM_FULL": "Комната заполнена.",
    "LOBBY_ROOM_NOT_FOUND": "Комната не найдена.",
    "LOBBY_INVALID_STATE": "В эту комнату нельзя войти.",
    "LOBBY_ALREADY_IN_ROOM": "Ты уже находишься в комнате",
    "LOBBY_WRONG_PASSWORD": "Неверный пароль.",
    "LOBBY_NOT_IN_ROOM": "Ты не находишься в комнате!",
    "LOBBY_LEAVE_NOTIFY": "🚪 Ты покинул комнату",
    "LOBBY_LEAVE_CONFIRM": "⚠️ Точно хочешь покинуть комнату?",
    "LOBBY_ONLY_OWNER": "Только владелец.",
    "LOBBY_DISBAND_CONFIRM": "🗑 Ты действительно хочешь удалить комнату <code>{code}</code>?\n\nОтправь, чтобы подтвердить:\n\n<code>/confirm {code}</code>",
    "LOBBY_DISBAND_MISMATCH": "Код не совпал. Расформирование отменено.",
    "LOBBY_DISBAND_NOTIFY": "🗑 Комната удалена.",
    "LOBBY_DISBAND_ONLY_OWNER": "Только владелец может удалить комнату.",
    "LOBBY_SETTINGS_ONLY_OWNER": "Только владелец может менять настройки.",
    "LOBBY_SETTINGS_ONLY_WAITING": "Настройки доступны только в статусе ожидания.",
    # --- чёрный список ---
    "LOBBY_BLACKLIST_ONLY_OWNER": "Только владелец может управлять чёрным списком.",
    "LOBBY_BLACKLIST_ONLY_WAITING": "Чёрный список доступен только в ожидании.",
    "LOBBY_KICK_ONLY_WAITING": "Исключение доступно только в ожидании.",
    "LOBBY_SELF_KICK": "Нельзя исключить самого себя.",
    "LOBBY_PLAYER_NOT_FOUND": "Участник с таким именем не найден в комнате.",
    "LOBBY_BLACKLIST_NOT_FOUND": "Участник с таким именем не найден в чёрном списке.",
    "LOBBY_KICK_FAIL": "Не удалось: {reason}",
    "CMD_KICK_USAGE": "Использование: /kick &lt;ник&gt;",
    "CMD_PARDON_USAGE": "Использование: /pardon &lt;ник&gt;",
    "BLACKLIST_KICK_PROMPT": "Выберите участника для исключения:",
    "BLACKLIST_PARDON_PROMPT": "Выберите участника для удаления из чёрного списка:",
    "BLACKLIST_KICK_NOTIFY": "⛔ Участник «{nick}» исключён и добавлен в чёрный список.",
    "BLACKLIST_PARDON_NOTIFY": "✅ «{nick}» убран из чёрного списка.",
    "BLACKLIST_KICK_DONE": "Участник исключён",
    "BLACKLIST_PARDON_DONE": "Убрано из ЧС",
    "BLACKLIST_TITLE": "<b>🚫 Чёрный список</b>",
    "BLACKLIST_EMPTY": "<b>🚫 Чёрный список</b>\n\nСписок пуст",
    "BLACKLIST_COUNT": "Заблокировано: {count}",
    "BLACKLIST_HINT": "<i>Нажми на имя, чтобы скопировать (или ввести в /pardon).</i>",
    # --- кастомные настройки (пример / точка расширения) ---
    "SETTINGS_PASSWORD_PROMPT": "Введи новый пароль — комната станет приватной. Либо «-», чтобы убрать пароль:",
    "SETTINGS_PASSWORD_ERROR": "Пароль должен быть от 1 до 64 символов, либо «-» чтобы убрать:",
    "LOBBY_CANT_CHANGE_PASSWORD": "Не удалось изменить пароль.",
    "LOBBY_CANT_SAVE": "Не удалось сохранить значение.",
    "LOBBY_SAVED": "Сохранено ✅",
    # --- уведомления о событиях (для notify_room_changed) ---
    "EVENT_PLAYER_JOINED": "👋 <b>{name}</b> присоединился к комнате",
    "EVENT_PLAYER_LEFT": "🚪 <b>{name}</b> покинул комнату",
    "EVENT_PLAYER_KICKED": "⛔ <b>{name}</b> исключён из комнаты",
    "EVENT_OWNER_CHANGED": "👑 Новый владелец комнаты: <b>{name}</b>",
    "EVENT_ROOM_DELETED": "🗑 Комната была удалена.",
    "EVENT_BLACKLIST_CHANGED": "🚫 Чёрный список комнаты изменён.",
    "EVENT_SETTINGS_UPDATED": "⚙️ Настройки комнаты обновлены.",
}

_EN: dict[str, Any] = {
    "CANCEL": "❌ Cancel",
    "BACK": "⬅️ Back",
    "PREV": "◀️",
    "NEXT": "▶️",
    "PAGINATION_PAGE": "📄 {cur}/{total}",
    "JOIN_BY_CODE": "By code",
    "JOIN_LIST": "📋 Room list",
    "MAIN_CREATE": "🎲 Create room",
    "MAIN_JOIN": "🔗 Find room",
    "MAIN_ROOMS": "📋 Room list",
    "SETTINGS": "⚙️ Settings",
    "LOBBY_LEAVE": "🚪 Leave",
    "LOBBY_BLACKLIST": "🚫 Blacklist",
    "BLACKLIST_ADD": "➕ Add",
    "BLACKLIST_REMOVE": "➖ Remove",
    "KICK_EMPTY": "No players",
    "PARDON_EMPTY": "The list is empty",
    "LEAVE_GO": "🚪 I am leaving",
    "LEAVE_STAY": "🙋 I am staying",
    "PRIVACY_PRIVATE": "🔒 Private",
    "PRIVACY_PUBLIC": "🌐 Open",
    "MENU_TITLE": "<b>Main menu</b>\nChoose an action:",
    "PLACEHOLDER": "This feature will be available in the next updates.",
    "GENERIC_ERROR": "Oops, something went wrong.",
    "ERR_BLACKLISTED": "🚫 You are in the blacklist of this room. Entry is denied.",
    "STATUS_TITLES": {
        "waiting": "Waiting for players",
        "starting": "Preparation",
        "playing": "The game is in progress",
        "finished": "Finished",
    },
    "ROOM_INFO_TITLE": "<b>🎲 {name}</b>",
    "ROOM_INFO_CODE": "Room code: <code>{code}</code>",
    "ROOM_INFO_PRIVACY_STATUS": "{privacy} | {status}",
    "ROOM_INFO_PLAYERS": "<b>Players ({cur}/{max}):</b>",
    "ROOM_INFO_MEMBER": "• <code>{name}</code>{suffix}",
    "ROOM_INFO_SETTINGS": "<b>Settings:</b>",
    "ROOM_INFO_SETTING_LINE": "• {field}: {value}",
    "ROOM_INFO_SETTINGS_EMPTY": "<i>No settings</i>",
    "ROOM_INFO_OWNER_MARK": "👑",
    "ROOM_INFO_BOT_MARK": "🤖",
    "ROOM_INFO_LEFT_MARK": "🚪",
    "CREATE_NAME_PROMPT": "Enter the room name:",
    "CREATE_NAME_ERROR": "The name must be 1 to 60 characters. Try again:",
    "CREATE_PRIVACY_PROMPT": "Is the room private?",
    "CREATE_PASSWORD_PROMPT": "Enter the room password:",
    "CREATE_PASSWORD_ERROR": "The password must be 1 to 64 characters. Try again:",
    "CREATE_MAX_PLAYERS_PROMPT": "Maximum players ({lo}–{hi}):",
    "CREATE_NUMBER_NAN": "Enter a number from {lo} to {hi}:",
    "CREATE_NUMBER_RANGE": "The number must be from {lo} to {hi}:",
    "CREATE_ALREADY_IN_ROOM": "You cannot create a room while you are in another room.",
    "JOIN_METHOD_PROMPT": "How do you want to join?",
    "JOIN_CODE_PROMPT": "Enter the room code:",
    "JOIN_CODE_EMPTY": "The code cannot be empty. Try again:",
    "JOIN_PRIVATE_NEED_PASSWORD": "🔒 This room is protected by a password. Enter it to join:",
    "JOIN_ROOMS_EMPTY": "There are no open rooms in waiting at the moment.",
    "JOIN_ROOMS_EMPTY_PAGE": "<b>📋 Public rooms</b> — page {cur}/{total}\n\nThe list is empty.",
    "JOIN_ROOMS_TITLE": "<b>📋 Public rooms</b> — page {cur}/{total}\n\nChoose a room to join:",
    "JOIN_PAGE_PROMPT": "Enter the page number (a number):",
    "JOIN_PAGE_NAN": "Enter an integer page number:",
    "JOIN_PAGE_EMPTY": "Page {page} is empty. Enter a number from 1 to {total}:",
    "JOIN_NO_ROOMS": "There are no public rooms at the moment.",
    "ROOM_LIST_LABEL": "{owner} - {name} - ({cur}/{max})",
    "LOBBY_ROOM_FULL": "The room is full.",
    "LOBBY_ROOM_NOT_FOUND": "Room not found.",
    "LOBBY_INVALID_STATE": "You cannot join this room.",
    "LOBBY_ALREADY_IN_ROOM": "You are already in a room",
    "LOBBY_WRONG_PASSWORD": "Wrong password.",
    "LOBBY_NOT_IN_ROOM": "You are not in a room!",
    "LOBBY_LEAVE_NOTIFY": "🚪 You left the room",
    "LOBBY_LEAVE_CONFIRM": "⚠️ Do you really want to leave the room?",
    "LOBBY_ONLY_OWNER": "Only the owner.",
    "LOBBY_DISBAND_CONFIRM": "🗑 Do you really want to delete room <code>{code}</code>?\n\nSend to confirm:\n\n<code>/confirm {code}</code>",
    "LOBBY_DISBAND_MISMATCH": "The code did not match. Disbanding is cancelled.",
    "LOBBY_DISBAND_NOTIFY": "🗑 Room deleted.",
    "LOBBY_DISBAND_ONLY_OWNER": "Only the owner can delete the room.",
    "LOBBY_SETTINGS_ONLY_OWNER": "Only the owner can change the settings.",
    "LOBBY_SETTINGS_ONLY_WAITING": "The settings are available only in the waiting status.",
    "LOBBY_BLACKLIST_ONLY_OWNER": "Only the owner can manage the blacklist.",
    "LOBBY_BLACKLIST_ONLY_WAITING": "The blacklist is available only while waiting.",
    "LOBBY_KICK_ONLY_WAITING": "Kick is available only while waiting.",
    "LOBBY_SELF_KICK": "You cannot kick yourself.",
    "LOBBY_PLAYER_NOT_FOUND": "A player with such a nickname is not found in the room.",
    "LOBBY_BLACKLIST_NOT_FOUND": "A player with such a nickname is not found in the blacklist.",
    "LOBBY_KICK_FAIL": "Failed: {reason}",
    "CMD_KICK_USAGE": "Usage: /kick &lt;nick&gt;",
    "CMD_PARDON_USAGE": "Usage: /pardon &lt;nick&gt;",
    "BLACKLIST_KICK_PROMPT": "Choose a player to kick:",
    "BLACKLIST_PARDON_PROMPT": "Choose a player to remove from the blacklist:",
    "BLACKLIST_KICK_NOTIFY": "⛔ Player «{nick}» was kicked and added to the blacklist.",
    "BLACKLIST_PARDON_NOTIFY": "✅ «{nick}» removed from the blacklist.",
    "BLACKLIST_KICK_DONE": "Player kicked",
    "BLACKLIST_PARDON_DONE": "Removed from the blacklist",
    "BLACKLIST_TITLE": "<b>🚫 Blacklist</b>",
    "BLACKLIST_EMPTY": "<b>🚫 Blacklist</b>\n\nThe list is empty",
    "BLACKLIST_COUNT": "Blocked: {count}",
    "BLACKLIST_HINT": "<i>Tap a nickname to copy it (or to enter it in /pardon).</i>",
    "SETTINGS_PASSWORD_PROMPT": "Enter a new password — the room will become private. Or «-» to remove it:",
    "SETTINGS_PASSWORD_ERROR": "The password must be 1 to 64 characters, or «-» to remove it:",
    "LOBBY_CANT_CHANGE_PASSWORD": "Failed to change the password.",
    "LOBBY_CANT_SAVE": "Failed to save the value.",
    "LOBBY_SAVED": "Saved ✅",
    "EVENT_PLAYER_JOINED": "👋 <b>{name}</b> joined the room",
    "EVENT_PLAYER_LEFT": "🚪 <b>{name}</b> left the room",
    "EVENT_PLAYER_KICKED": "⛔ <b>{name}</b> was excluded from the room",
    "EVENT_OWNER_CHANGED": "👑 New room owner: <b>{name}</b>",
    "EVENT_ROOM_DELETED": "🗑 The room was deleted.",
    "EVENT_BLACKLIST_CHANGED": "🚫 The room blacklist has changed.",
    "EVENT_SETTINGS_UPDATED": "⚙️ Room settings updated.",
}


class TextProvider(Protocol):
    """Любой объект, умеющий отдавать строки и таблицы локали.

    Имена параметров намеренно не ``lang``/``key``: тогда плейсхолдеры
    ``{key}`` / ``{lang}`` в пользовательских текстах не конфликтуют с
    аргументами вызова ``get(lang, key, **kwargs)``.
    """

    def get(self, _language: str, _text_key: str, **kwargs: Any) -> str: ...

    def table(self, _language: str, _text_key: str) -> dict[str, Any]: ...

    def status_title(self, _language: str, status: str) -> str: ...


class DefaultTexts:
    """Встроенный провайдер: словари RU/EN + переопределения хоста."""

    def __init__(
        self,
        overrides: dict[str, dict[str, Any]] | None = None,
        default_lang: str = "ru",
    ) -> None:
        self.default_lang = default_lang
        self._tables: dict[str, dict[str, Any]] = {
            "ru": dict(_RU),
            "en": dict(_EN),
        }
        for lang, table in (overrides or {}).items():
            self._tables.setdefault(lang, {}).update(table)

    def _table(self, lang: str) -> dict[str, Any]:
        return self._tables.get(lang) or self._tables.get(self.default_lang, {})

    def get(self, _language: str, _text_key: str, **kwargs: Any) -> str:
        val = self._table(_language).get(_text_key, _MISSING)
        if val is _MISSING:
            val = self._table(self.default_lang).get(_text_key, _MISSING)
        if val is _MISSING:
            return _text_key
        if isinstance(val, dict):
            return str(val)
        if kwargs:
            try:
                return str(val).format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return str(val)
        return str(val)

    def table(self, _language: str, _text_key: str) -> dict[str, Any]:
        val = self._table(_language).get(_text_key, _MISSING)
        if val is _MISSING:
            val = self._table(self.default_lang).get(_text_key, {})
        return dict(val) if isinstance(val, dict) else {}

    def status_title(self, _language: str, status: str) -> str:
        titles = self.table(_language, "STATUS_TITLES")
        return str(titles.get(status, status))


class _CallableTexts:
    """Обёртка над функцией ``(lang, key, **kwargs) -> str``."""

    def __init__(self, fn: Callable[..., str]) -> None:
        self._fn = fn

    def get(self, _language: str, _text_key: str, **kwargs: Any) -> str:
        return self._fn(_language, _text_key, **kwargs)

    def table(self, _language: str, _text_key: str) -> dict[str, Any]:
        return {}

    def status_title(self, _language: str, status: str) -> str:
        return status


def make_texts(
    spec: Any,
    overrides: dict[str, dict[str, Any]] | None = None,
    default_lang: str = "ru",
) -> TextProvider:
    """Собирает провайдер текстов из конфигурации ``RoomsConfig.texts``."""
    if spec is None:
        return DefaultTexts(overrides=overrides, default_lang=default_lang)
    if callable(spec) and not hasattr(spec, "get"):
        return _CallableTexts(spec)
    return spec  #type: ignore[return-value]
