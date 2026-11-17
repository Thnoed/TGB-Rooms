"""Конфигурация системы комнат и хуки жизненного цикла.

Один объект ``RoomsConfig`` описывает всё поведение библиотеки: размеры и
лимиты, команды, тексты, точки расширения и колбэки. Ничего не читается из
``.env`` — хост сам решает, откуда брать значения.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from aiogram import Router

from .extensions import CreateStep, LobbyButton
from .models import Principal, Room
from .texts import EVENT_TEXT_KEYS, TextProvider

Hook = Callable[..., Any]  # sync или async: (*, rooms, principal, room, **payload)

DEFAULT_COMMANDS: dict[str, list[str]] = {
    "create": ["create", "createroom", "newroom"],
    "join": ["join", "joinroom"],
    "rooms": ["rooms", "roomlist"],
    "leave": ["leave"],
    "disband": ["disband"],
    "confirm": ["confirm"],
    "kick": ["kick"],
    "pardon": ["pardon"],
}

DEFAULT_CANCEL_TEXTS = frozenset({
    "❌ Отмена", "❌ Cancel", "Отмена", "отмена", "Cancel", "cancel", "/cancel",
})


@dataclass
class Hooks:
    """Хуки жизненного цикла (все необязательны, можно sync или async).

    Сигнатура: ``await hook(rooms=..., principal=..., room=..., **payload)``.
    Для внешних событий (WS) ``principal`` может быть ``None``, а ``room`` —
    снимком комнаты или ``None``. Исключения хуков логируются и не роняют
    обработчик; при этом вызывается ``on_error``.
    """

    on_room_created: Hook | None = None
    on_room_joined: Hook | None = None
    on_room_left: Hook | None = None
    on_room_disbanded: Hook | None = None
    on_room_deleted: Hook | None = None
    on_room_changed: Hook | None = None
    on_member_joined: Hook | None = None
    on_member_left: Hook | None = None
    on_member_kicked: Hook | None = None
    on_member_pardoned: Hook | None = None
    on_owner_changed: Hook | None = None
    on_blacklist_changed: Hook | None = None
    on_settings_changed: Hook | None = None
    on_error: Hook | None = None


@dataclass
class RoomsConfig:
    """Все настройки ``Rooms``. Значения по умолчанию = поведение исходного бота."""

    # --- язык и тексты ---
    default_language: str = "ru"
    texts: TextProvider | Callable[..., str] | None = None
    text_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)

    # --- лимиты и размеры ---
    rooms_page_size: int = 10
    name_min_len: int = 1
    name_max_len: int = 60
    password_min_len: int = 1
    password_max_len: int = 64
    default_max_players: int = 8
    max_players_min: int = 2
    max_players_max: int = 100
    code_length: int = 6
    code_factory: Callable[[], str] | None = None

    # --- UI ---
    notice_lifetime: float = 12.0
    max_button_len: int = 60
    parse_mode: str = "HTML"
    delete_menu_on_action: bool = True

    # --- команды и колбэки ---
    commands: dict[str, list[str]] = field(
        default_factory=lambda: {k: list(v) for k, v in DEFAULT_COMMANDS.items()}
    )
    cancel_texts: frozenset[str] = DEFAULT_CANCEL_TEXTS
    callback_prefix: str = "tgr"

    # --- интеграция с ботом-хостом ---
    identity_resolver: Callable[[Any, dict], Any] | None = None
    language_resolver: Callable[[int, dict], Any] | None = None
    bot: Any = None

    # --- статусы ---
    joinable_statuses: frozenset[str] = frozenset({"waiting"})
    editable_statuses: frozenset[str] = frozenset({"waiting"})
    can_manage: Callable[[Room, Principal], bool | Awaitable[bool]] | None = None
    needs_leave_confirm: Callable[[Room, Principal], bool | Awaitable[bool]] | None = None

    # --- рендеринг главного сообщения ---
    room_info_renderer: Callable[..., str | Awaitable[str]] | None = None
    settings_summary: Callable[..., list[str] | Awaitable[list[str]]] | None = None

    # --- точки расширения ---
    create_steps: list[CreateStep] = field(default_factory=list)
    settings_extension: Any = None
    extra_lobby_buttons: list[LobbyButton] = field(default_factory=list)
    extra_routers: list[Router] = field(default_factory=list)
    on_show_menu: Callable[..., Awaitable[None]] | None = None

    # --- события / уведомления ---
    hooks: Hooks = field(default_factory=Hooks)
    notify_events: bool = False
    # По умолчанию — копия EVENT_TEXT_KEYS из texts.py (там же живут тексты).
    event_text_keys: dict[str, str] = field(default_factory=lambda: dict(EVENT_TEXT_KEYS))
