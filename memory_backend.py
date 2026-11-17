"""Автономный in-memory бэкенд комнат (по умолчанию, без внешних сервисов).

Реализует весь контракт ``RoomsBackend``: создание, вход по ключу, список
активных комнат, выход, расформирование, чёрный список, смену владельца,
произвольные настройки и пароль. Состояние живёт в процессе бота — для
персистентности/кластеризации напишите свой бэкенд или возьмите
``RestRoomsBackend``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Callable

from .backend import (
    ERR_ACCESS_DENIED,
    ERR_ALREADY_IN_ROOM,
    ERR_FORBIDDEN,
    ERR_INVALID_ROOM_STATE,
    ERR_PLAYER_NOT_FOUND,
    ERR_ROOM_FULL,
    ERR_ROOM_NOT_FOUND,
    ERR_SELF_KICK,
    RoomsBackend,
)
from .models import (
    ACTIVE,
    KICKED,
    LEFT,
    Member,
    Principal,
    Room,
    RoomDraft,
    RoomResult,
)
from .utils import random_code

logger = logging.getLogger(__name__)


class MemoryRoomsBackend(RoomsBackend):
    """Комнаты в памяти процесса. Потокобезопасно внутри одного event loop."""

    def __init__(
        self,
        *,
        code_length: int = 6,
        code_factory: Callable[[], str] | None = None,
        joinable_statuses: frozenset[str] | set[str] = frozenset({"waiting"}),
        default_status: str = "waiting",
    ) -> None:
        self._rooms: dict[str, Room] = {}
        self._passwords: dict[str, str | None] = {}
        self._membership: dict[str, str] = {}  # player_id -> room_code
        self._lock = asyncio.Lock()
        self._code_length = code_length
        self._code_factory = code_factory
        self._joinable_statuses = frozenset(joinable_statuses)
        self._default_status = default_status

    # --- служебное -----------------------------------------------------------

    def _new_code(self) -> str:
        for _ in range(200):
            code = (
                self._code_factory()
                if self._code_factory is not None
                else random_code(self._code_length)
            )
            code = str(code).strip().upper()
            if code and code not in self._rooms:
                return code
        raise RuntimeError("Не удалось сгенерировать уникальный код комнаты")

    def _snapshot(self, room: Room) -> Room:
        """Копия без пароля, но с флагом ``has_password``."""
        return replace(
            room,
            members=[replace(m, extra=dict(m.extra)) for m in room.members],
            blacklist=list(room.blacklist),
            settings=dict(room.settings),
            extra=dict(room.extra),
            has_password=self._passwords.get(room.code) is not None,
        )

    def _new_member(self, principal: Principal) -> Member:
        return Member(
            player_id=principal.player_id,
            display_name=principal.display_name or principal.player_id,
            extra=dict(principal.extra or {}),
        )

    async def _forget(self, code: str) -> None:
        room = self._rooms.pop(code, None)
        self._passwords.pop(code, None)
        if room is not None:
            for member in room.members:
                if self._membership.get(member.player_id) == code:
                    self._membership.pop(member.player_id, None)

    # --- контракт ------------------------------------------------------------

    async def create_room(self, principal: Principal, draft: RoomDraft) -> RoomResult:
        async with self._lock:
            if principal.player_id in self._membership:
                return RoomResult.fail(ERR_ALREADY_IN_ROOM)
            code = self._new_code()
            password = draft.password if draft.password not in (None, "") else None
            room = Room(
                code=code,
                name=draft.name,
                owner_id=principal.player_id,
                is_private=bool(draft.is_private or password),
                max_players=max(1, int(draft.max_players)),
                status=self._default_status,
                members=[self._new_member(principal)],
                settings=dict(draft.settings),
                extra=dict(draft.extra),
            )
            room.extra.setdefault("owner_display", principal.display_name or principal.player_id)
            self._rooms[code] = room
            self._passwords[code] = password
            self._membership[principal.player_id] = code
            logger.debug("Создана комната %s (%s)", code, room.name)
            return RoomResult.success(self._snapshot(room))

    async def join_room(
        self, principal: Principal, code: str, password: str | None = None
    ) -> RoomResult:
        code = (code or "").strip().upper()
        async with self._lock:
            room = self._rooms.get(code)
            if room is None:
                return RoomResult.fail(ERR_ROOM_NOT_FOUND)
            if principal.player_id in room.blacklist:
                return RoomResult.fail(ERR_ACCESS_DENIED, blacklisted=True)
            stored = self._passwords.get(code)
            if stored is not None and password != stored:
                return RoomResult.fail(ERR_ACCESS_DENIED, password_required=True)
            if room.status not in self._joinable_statuses:
                return RoomResult.fail(ERR_INVALID_ROOM_STATE)
            if room.is_full():
                return RoomResult.fail(ERR_ROOM_FULL)
            current = self._membership.get(principal.player_id)
            if current and current != code:
                return RoomResult.fail(ERR_ALREADY_IN_ROOM)
            member = room.member(principal.player_id)
            if member is None:
                room.members.append(self._new_member(principal))
            else:
                member.state = ACTIVE
                member.display_name = principal.display_name or member.display_name
            self._membership[principal.player_id] = code
            return RoomResult.success(self._snapshot(room))

    async def leave_room(self, principal: Principal, code: str) -> RoomResult:
        code = (code or "").strip().upper()
        async with self._lock:
            room = self._rooms.get(code)
            if room is None:
                return RoomResult.fail(ERR_ROOM_NOT_FOUND)
            member = room.member(principal.player_id)
            if member is not None:
                member.state = LEFT
            self._membership.pop(principal.player_id, None)
            owner_changed: str | None = None
            if room.owner_id == principal.player_id:
                remaining = room.active_members()
                if remaining:
                    room.owner_id = remaining[0].player_id
                    owner_changed = remaining[0].player_id
                else:
                    await self._forget(code)
                    return RoomResult.success(None, room_deleted=True)
            return RoomResult.success(self._snapshot(room), owner_changed=owner_changed)

    async def disband_room(self, principal: Principal, code: str) -> RoomResult:
        code = (code or "").strip().upper()
        async with self._lock:
            room = self._rooms.get(code)
            if room is None:
                return RoomResult.fail(ERR_ROOM_NOT_FOUND)
            if room.owner_id != principal.player_id:
                return RoomResult.fail(ERR_FORBIDDEN)
            members = [m.player_id for m in room.members]
            await self._forget(code)
            return RoomResult.success(None, members=members)

    async def get_room(self, principal: Principal, code: str) -> Room | None:
        code = (code or "").strip().upper()
        async with self._lock:
            room = self._rooms.get(code)
            return self._snapshot(room) if room is not None else None

    async def list_rooms(
        self,
        principal: Principal,
        limit: int,
        offset: int,
        statuses: frozenset[str] | set[str] | None = None,
    ) -> tuple[list[Room], int]:
        statuses = frozenset(statuses or self._joinable_statuses)
        async with self._lock:
            items = [
                r
                for r in self._rooms.values()
                if not r.is_private
                and r.status in statuses
                and not r.is_full()
            ]
            items.sort(key=lambda r: r.created_at, reverse=True)
            total = len(items)
            page = [self._snapshot(r) for r in items[offset : offset + limit]]
            return page, total

    async def get_blacklist(self, principal: Principal, code: str) -> list[str]:
        code = (code or "").strip().upper()
        async with self._lock:
            room = self._rooms.get(code)
            return list(room.blacklist) if room is not None else []

    async def check_blacklist(self, principal: Principal, code: str) -> bool:
        code = (code or "").strip().upper()
        async with self._lock:
            room = self._rooms.get(code)
            return room is not None and principal.player_id in room.blacklist

    async def kick(
        self, principal: Principal, code: str, target_player_id: str
    ) -> RoomResult:
        code = (code or "").strip().upper()
        async with self._lock:
            room = self._rooms.get(code)
            if room is None:
                return RoomResult.fail(ERR_ROOM_NOT_FOUND)
            if room.owner_id != principal.player_id:
                return RoomResult.fail(ERR_FORBIDDEN)
            if room.status not in self._joinable_statuses:
                return RoomResult.fail(ERR_INVALID_ROOM_STATE)
            if target_player_id == principal.player_id:
                return RoomResult.fail(ERR_SELF_KICK)
            target = room.member(target_player_id)
            if target is None or not target.is_active:
                return RoomResult.fail(ERR_PLAYER_NOT_FOUND)
            target.state = KICKED
            if target_player_id not in room.blacklist:
                room.blacklist.append(target_player_id)
            if self._membership.get(target_player_id) == code:
                self._membership.pop(target_player_id, None)
            return RoomResult.success(
                self._snapshot(room),
                target_player_id=target_player_id,
                target_display_name=target.display_name,
            )

    async def pardon(
        self, principal: Principal, code: str, target_player_id: str
    ) -> RoomResult:
        code = (code or "").strip().upper()
        async with self._lock:
            room = self._rooms.get(code)
            if room is None:
                return RoomResult.fail(ERR_ROOM_NOT_FOUND)
            if room.owner_id != principal.player_id:
                return RoomResult.fail(ERR_FORBIDDEN)
            room.blacklist = [x for x in room.blacklist if x != target_player_id]
            return RoomResult.success(self._snapshot(room), target_player_id=target_player_id)

    async def update_settings(
        self, principal: Principal, code: str, settings: dict
    ) -> RoomResult:
        code = (code or "").strip().upper()
        async with self._lock:
            room = self._rooms.get(code)
            if room is None:
                return RoomResult.fail(ERR_ROOM_NOT_FOUND)
            if room.owner_id != principal.player_id:
                return RoomResult.fail(ERR_FORBIDDEN)
            room.settings.update(dict(settings or {}))
            return RoomResult.success(self._snapshot(room))

    async def set_password(
        self, principal: Principal, code: str, password: str | None
    ) -> RoomResult:
        code = (code or "").strip().upper()
        async with self._lock:
            room = self._rooms.get(code)
            if room is None:
                return RoomResult.fail(ERR_ROOM_NOT_FOUND)
            if room.owner_id != principal.player_id:
                return RoomResult.fail(ERR_FORBIDDEN)
            password = str(password) if password not in (None, "") else None
            self._passwords[code] = password
            room.is_private = password is not None
            return RoomResult.success(self._snapshot(room))

    # --- утилиты для хоста ---------------------------------------------------

    async def set_status(self, code: str, status: str) -> Room | None:
        """Сменить статус комнаты (например, ``waiting → playing``)."""
        async with self._lock:
            room = self._rooms.get(code)
            if room is None:
                return None
            room.status = status
            return self._snapshot(room)

    def get_active_rooms(self) -> dict[str, Room]:
        """``{code: снимок}`` — для синхронизации внешних WS-клиентов."""
        return {code: self._snapshot(room) for code, room in self._rooms.items()}
