"""Форматирование сообщений системы комнат.

Вынесено из ``app/messages/lobby.py`` (``format_lobby_message``,
``format_blacklist_message``) и ``app/handlers/room.py``
(``_rooms_list_text``). Рендереры принимают typed-модели и ``TextProvider``,
поэтому их легко заменить через ``RoomsConfig.room_info_renderer``.
"""

from __future__ import annotations

from typing import Callable

from .models import LEFT, Principal, Room
from .texts import TextProvider
from .utils import escape_html


def format_lobby_message(
    room: Room,
    principal: Principal,
    texts: TextProvider,
    lang: str,
    *,
    settings_lines: list[str] | None = None,
    extra_lines: list[str] | None = None,
    display_name_resolver: Callable[[str], str | None] | None = None,
) -> str:
    """Главное сообщение комнаты: название, ключ, тип, статус, участники.

    Плюс опциональные строки настроек (``settings_summary`` хоста) и любые
    ``extra_lines``. Все пользовательские данные экранируются под HTML.
    """
    privacy = texts.get(lang, "PRIVACY_PRIVATE" if room.is_private else "PRIVACY_PUBLIC")
    status = texts.status_title(lang, room.status)

    lines = [
        texts.get(lang, "ROOM_INFO_TITLE", name=escape_html(room.name)),
        texts.get(lang, "ROOM_INFO_CODE", code=escape_html(room.code)),
        texts.get(lang, "ROOM_INFO_PRIVACY_STATUS", privacy=privacy, status=escape_html(status)),
        "",
        texts.get(lang, "ROOM_INFO_PLAYERS", cur=len(room.active_members()), max=room.max_players),
    ]

    for member in room.members:
        name = member.label
        if display_name_resolver is not None:
            try:
                cached = display_name_resolver(member.player_id)
            except Exception:
                cached = None
            if cached:
                name = cached
        marks: list[str] = []
        if room.is_owner(member.player_id):
            marks.append(texts.get(lang, "ROOM_INFO_OWNER_MARK"))
        if member.is_bot:
            marks.append(texts.get(lang, "ROOM_INFO_BOT_MARK"))
        if member.state == LEFT:
            marks.append(texts.get(lang, "ROOM_INFO_LEFT_MARK"))
        suffix = f" {' '.join(marks)}" if marks else ""
        lines.append(
            texts.get(lang, "ROOM_INFO_MEMBER", name=escape_html(name), suffix=suffix)
        )

    if settings_lines:
        lines += ["", texts.get(lang, "ROOM_INFO_SETTINGS"), *settings_lines]
    for line in extra_lines or []:
        lines.append(line)
    return "\n".join(lines)


def default_settings_lines(room: Room, texts: TextProvider, lang: str) -> list[str]:
    """Стандартный summary настроек: по строке на ключ ``room.settings``."""
    return [
        texts.get(lang, "ROOM_INFO_SETTING_LINE", field=escape_html(k), value=escape_html(v))
        for k, v in (room.settings or {}).items()
    ]


def format_blacklist_message(
    blacklist: list[str],
    texts: TextProvider,
    lang: str,
    display_name_resolver: Callable[[str], str | None] | None = None,
) -> str:
    """Экран чёрного списка (редактирует главное сообщение комнаты)."""
    if not blacklist:
        return texts.get(lang, "BLACKLIST_EMPTY")
    lines = [
        texts.get(lang, "BLACKLIST_TITLE"),
        "",
        texts.get(lang, "BLACKLIST_COUNT", count=len(blacklist)),
        "",
    ]
    for entry in blacklist:
        name = None
        if display_name_resolver is not None:
            try:
                name = display_name_resolver(entry)
            except Exception:
                name = None
        lines.append(f"• <code>{escape_html(name or entry)}</code>")
    hint = texts.get(lang, "BLACKLIST_HINT")
    if hint and hint != "BLACKLIST_HINT":
        lines += ["", f"<i>{hint}</i>"]
    return "\n".join(lines)


def rooms_list_text(
    items: list[Room],
    page: int,
    total: int,
    limit: int,
    texts: TextProvider,
    lang: str,
) -> str:
    """Заголовок страницы списка активных комнат."""
    total_pages = max(1, (total + limit - 1) // limit)
    if not items:
        return texts.get(lang, "JOIN_ROOMS_EMPTY_PAGE", cur=page + 1, total=total_pages)
    return texts.get(lang, "JOIN_ROOMS_TITLE", cur=page + 1, total=total_pages)
