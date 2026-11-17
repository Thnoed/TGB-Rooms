"""Доменные модели абстрактной системы комнат.

Модели не зависят от aiogram и от конкретного бэкенда: ``RoomsBackend``
оперирует ими, UI-слой (рендереры, клавиатуры) читает их, хуки получают их
в качестве аргументов. Никакой игровой логики здесь нет — только «комната».
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

#: Стандартные статусы участника. Бэкенд волен использовать свои строки.
ACTIVE = "active"
LEFT = "left"
KICKED = "kicked"


@dataclass
class Member:
    """Участник комнаты."""

    player_id: str
    display_name: str = ""
    is_bot: bool = False
    state: str = ACTIVE
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.state == ACTIVE

    @property
    def label(self) -> str:
        return self.display_name or self.player_id

    def as_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "display_name": self.display_name,
            "is_bot": self.is_bot,
            "state": self.state,
            "extra": dict(self.extra),
        }


@dataclass
class Room:
    """Комната. Сам пароль сюда не попадает — его хранит бэкенд.

    ``settings`` и ``extra`` — произвольные словари под конкретный проект:
    именно туда кладутся любые кастомные настройки комнаты.
    """

    code: str
    name: str
    owner_id: str
    is_private: bool = False
    has_password: bool = False
    max_players: int = 8
    status: str = "waiting"
    members: list[Member] = field(default_factory=list)
    blacklist: list[str] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    extra: dict[str, Any] = field(default_factory=dict)

    def active_members(self) -> list[Member]:
        return [m for m in self.members if m.is_active]

    def member(self, player_id: str) -> Member | None:
        return next((m for m in self.members if m.player_id == player_id), None)

    def is_owner(self, player_id: str) -> bool:
        return self.owner_id == player_id

    def is_full(self) -> bool:
        return len(self.active_members()) >= self.max_players

    def is_joinable(self, statuses: set[str] | frozenset[str]) -> bool:
        return self.status in statuses and not self.is_full()

    def as_dict(self) -> dict[str, Any]:
        """Плоский снимок (близко к ``get_room_state`` исходного бота).

        Удобно для кастомных рендереров, перенесённых из ``shelter-tgbot``.
        """
        return {
            "code": self.code,
            "name": self.name,
            "owner_id": self.owner_id,
            "is_private": self.is_private,
            "has_password": self.has_password,
            "max_players": self.max_players,
            "status": self.status,
            "players": [m.as_dict() for m in self.members],
            "blacklist": list(self.blacklist),
            "settings": dict(self.settings),
            "created_at": self.created_at,
            "extra": dict(self.extra),
        }


@dataclass
class RoomDraft:
    """Черновик комнаты, который собирает мастер создания.

    Базовые шаги заполняют ``name`` / ``is_private`` / ``password``;
    кастомные шаги (``CreateStep``) пишут в ``settings``, ``extra`` или
    переопределяют ``max_players``.
    """

    name: str = ""
    is_private: bool = False
    password: str | None = None
    max_players: int = 8
    settings: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoomResult:
    """Результат операции бэкенда.

    Аналог словаря ``{"error": True, "code": ...}`` из ``shelter-tgbot``,
    но типизированный и с готовым снимком комнаты при успехе.
    """

    ok: bool
    room: Room | None = None
    code: str = ""
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, room: Room | None = None, **data: Any) -> "RoomResult":
        return cls(ok=True, room=room, data=data)

    @classmethod
    def fail(cls, code: str, message: str = "", **data: Any) -> "RoomResult":
        return cls(ok=False, code=code, message=message, data=data)

    @property
    def error(self) -> bool:
        return not self.ok


@dataclass
class Identity:
    """Идентичность пользователя, которую отдаёт ``identity_resolver`` хоста.

    ``player_id`` — ключ, под которым пользователь известен бэкенду комнаты
    (по умолчанию ``str(telegram_id)``). ``token`` нужен только REST-бэкенду.
    """

    user_id: int
    player_id: str
    display_name: str = ""
    token: str | None = None
    language: str = "ru"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Principal:
    """Пользователь бота в терминах системы комнат (identity + привязка)."""

    user_id: int
    player_id: str
    display_name: str = ""
    token: str | None = None
    language: str = "ru"
    room_code: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class UserBinding:
    """Локальная привязка пользователя к комнате и служебным сообщениям.

    Абстракция над ``UserData`` / ``BotStorage`` исходного бота: здесь лежат
    только те поля, которые нужны системе комнат.
    """

    user_id: int
    player_id: str = ""
    display_name: str = ""
    token: str | None = None
    language: str = "ru"
    room_code: str | None = None
    lobby_message_id: int | None = None
    menu_message_id: int | None = None
    blacklist_view: bool = False
    blacklist_add_message_id: int | None = None
    blacklist_remove_message_id: int | None = None
    settings_open: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def as_principal(self) -> Principal:
        return Principal(
            user_id=self.user_id,
            player_id=self.player_id or str(self.user_id),
            display_name=self.display_name,
            token=self.token,
            language=self.language,
            room_code=self.room_code,
            extra=dict(self.extra),
        )
