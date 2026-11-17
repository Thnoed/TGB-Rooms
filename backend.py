"""Контракт бэкенда комнат.

``RoomsBackend`` — единственная точка, где система комнат соприкасается с
хранением/сервером. Всё остальное (FSM, клавиатуры, сообщения, чёрный список)
работает поверх этого контракта и не знает, in-memory это или REST API.

Коды ошибок совпадают с кодами ``shelter-core`` (``room_full``,
``room_access_denied`` и т.д.), чтобы тексты и адаптер были переносимыми.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import Principal, Room, RoomDraft, RoomResult

# --- Коды ошибок (мапятся на тексты через ERROR_TEXT_KEYS в texts.py) ---
ERR_ROOM_NOT_FOUND = "room_not_found"
ERR_ROOM_FULL = "room_full"
ERR_INVALID_ROOM_STATE = "invalid_room_state"
ERR_ALREADY_IN_ROOM = "already_in_room"
ERR_ACCESS_DENIED = "room_access_denied"
ERR_FORBIDDEN = "forbidden"
ERR_PLAYER_NOT_FOUND = "player_not_found"
ERR_SELF_KICK = "self_kick"
ERR_NOT_SUPPORTED = "not_supported"
ERR_CONNECTION = "connection_error"


class RoomsBackend(ABC):
    """Асинхронный контракт хранилища комнат.

    Реализуйте его под свой проект или возьмите готовые
    ``MemoryRoomsBackend`` / ``RestRoomsBackend``. Необязательные методы
    (``update_settings``, ``set_password``) по умолчанию возвращают
    ``not_supported`` — минимальный бэкенд может их не реализовывать.

    Все методы получают ``Principal``: в нём есть ``player_id`` (ключ
    участника), ``token`` (для REST), ``display_name`` и ``user_id``.
    """

    @abstractmethod
    async def create_room(self, principal: Principal, draft: RoomDraft) -> RoomResult:
        """Создать комнату. Успех → ``RoomResult`` со снимком комнаты."""

    @abstractmethod
    async def join_room(
        self, principal: Principal, code: str, password: str | None = None
    ) -> RoomResult:
        """Войти по ключу.

        При ``room_access_denied`` в ``result.data`` желательно положить
        ``blacklisted=True`` (тогда бот сразу покажет «вы в ЧС») или
        ``password_required=True`` (тогда бот спросит пароль).
        """

    @abstractmethod
    async def leave_room(self, principal: Principal, code: str) -> RoomResult:
        """Покинуть комнату. В ``data`` можно вернуть ``owner_changed`` /
        ``room_deleted`` — система разошлёт хуки и обновит лобби."""

    @abstractmethod
    async def disband_room(self, principal: Principal, code: str) -> RoomResult:
        """Удалить комнату (только владелец)."""

    @abstractmethod
    async def get_room(self, principal: Principal, code: str) -> Room | None:
        """Снимок состояния комнаты или ``None``."""

    @abstractmethod
    async def list_rooms(
        self,
        principal: Principal,
        limit: int,
        offset: int,
        statuses: frozenset[str] | set[str] | None = None,
    ) -> tuple[list[Room], int]:
        """Активные комнаты, к которым можно подключиться → (страница, всего).

        Возвращать стоит только открытые комнаты в статусе ``statuses``
        и с свободными местами. Элементы могут быть «неполными» снимками:
        для списка достаточно ``code``, ``name``, ``owner_id``,
        ``max_players``, ``members`` (для счётчика) и ``status``.
        """

    @abstractmethod
    async def get_blacklist(self, principal: Principal, code: str) -> list[str]:
        """Список ``player_id`` в чёрном списке комнаты."""

    @abstractmethod
    async def check_blacklist(self, principal: Principal, code: str) -> bool:
        """Находится ли текущий пользователь в ЧС комнаты."""

    @abstractmethod
    async def kick(
        self, principal: Principal, code: str, target_player_id: str
    ) -> RoomResult:
        """Исключить участника и занести его ``player_id`` в ЧС."""

    @abstractmethod
    async def pardon(
        self, principal: Principal, code: str, target_player_id: str
    ) -> RoomResult:
        """Убрать ``player_id`` из ЧС."""

    # --- Необязательные операции (кастомные настройки) ---

    async def update_settings(
        self, principal: Principal, code: str, settings: dict
    ) -> RoomResult:
        """Обновить произвольные настройки комнаты. Переопределяется хостом."""
        return RoomResult.fail(ERR_NOT_SUPPORTED, "update_settings is not implemented")

    async def set_password(
        self, principal: Principal, code: str, password: str | None
    ) -> RoomResult:
        """Сменить пароль / сделать комнату открытой. Переопределяется хостом."""
        return RoomResult.fail(ERR_NOT_SUPPORTED, "set_password is not implemented")
