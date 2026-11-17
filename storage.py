"""Локальная привязка пользователей к комнатам.

Абстракция над ``BotStorage`` из ``shelter-tgbot``: хранит только то, что
нужно системе комнат (текущая комната, id главного сообщения, временные
сообщения ЧС, язык, кэш display-имён). Хост может подменить хранилище
своим адаптером поверх БД, реализовав ``RoomsStorage``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace

from .models import UserBinding


class RoomsStorage(ABC):
    """Контракт локального хранилища привязок."""

    @abstractmethod
    async def get_binding(self, user_id: int) -> UserBinding | None:
        """Прочитать привязку (``None`` — пользователь ещё не встречался)."""

    @abstractmethod
    async def set_binding(self, binding: UserBinding) -> None:
        """Полностью записать привязку."""

    @abstractmethod
    async def update_binding(self, user_id: int, **kwargs) -> UserBinding | None:
        """Частично обновить привязку, создав её при отсутствии."""

    @abstractmethod
    async def clear_room(self, user_id: int) -> None:
        """Сбросить всё, что относится к текущей комнате."""

    @abstractmethod
    async def get_users_in_room(self, code: str) -> list[UserBinding]:
        """Все пользователи бота, привязанные к комнате."""

    @abstractmethod
    async def get_display_name(self, player_id: str) -> str | None:
        """Кэш имени участника (нужен для экрана ЧС после выхода)."""

    @abstractmethod
    async def set_display_name(self, player_id: str, name: str) -> None:
        """Запомнить имя участника."""

    @abstractmethod
    async def get_language(self, user_id: int) -> str:
        """Язык интерфейса пользователя."""

    @abstractmethod
    async def set_language(self, user_id: int, lang: str) -> None:
        """Сохранить язык интерфейса пользователя."""


class InMemoryRoomsStorage(RoomsStorage):
    """Простая реализация в памяти (по умолчанию, без зависимостей)."""

    def __init__(self) -> None:
        self._bindings: dict[int, UserBinding] = {}
        self._names: dict[str, str] = {}

    @staticmethod
    def _copy(binding: UserBinding) -> UserBinding:
        return replace(binding, extra=dict(binding.extra))

    async def get_binding(self, user_id: int) -> UserBinding | None:
        binding = self._bindings.get(user_id)
        return self._copy(binding) if binding is not None else None

    async def set_binding(self, binding: UserBinding) -> None:
        self._bindings[binding.user_id] = self._copy(binding)

    async def update_binding(self, user_id: int, **kwargs) -> UserBinding | None:
        binding = self._bindings.get(user_id)
        if binding is None:
            binding = UserBinding(user_id=user_id)
        try:
            updated = replace(binding, **kwargs)
        except TypeError as exc:
            raise TypeError(f"Неизвестное поле привязки: {exc}") from exc
        self._bindings[user_id] = self._copy(updated)
        return self._copy(updated)

    async def clear_room(self, user_id: int) -> None:
        binding = self._bindings.get(user_id)
        if binding is None:
            return
        self._bindings[user_id] = replace(
            binding,
            room_code=None,
            lobby_message_id=None,
            blacklist_view=False,
            blacklist_add_message_id=None,
            blacklist_remove_message_id=None,
            settings_open=False,
        )

    async def get_users_in_room(self, code: str) -> list[UserBinding]:
        return [
            self._copy(b)
            for b in self._bindings.values()
            if b.room_code == code
        ]

    async def get_display_name(self, player_id: str) -> str | None:
        return self._names.get(player_id)

    async def set_display_name(self, player_id: str, name: str) -> None:
        if player_id and name:
            self._names[player_id] = name

    async def get_language(self, user_id: int) -> str:
        binding = self._bindings.get(user_id)
        return binding.language if binding is not None else "ru"

    async def set_language(self, user_id: int, lang: str) -> None:
        await self.update_binding(user_id, language=lang)

    def get_active_rooms(self) -> dict[str, UserBinding]:
        """``{code: первый пользователь}`` — для синхронизации WS-клиентов."""
        rooms: dict[str, UserBinding] = {}
        for binding in self._bindings.values():
            if binding.room_code and binding.room_code not in rooms:
                rooms[binding.room_code] = self._copy(binding)
        return rooms

    def stats(self) -> dict[str, int]:
        return {"users": len(self._bindings), "rooms": len(self.get_active_rooms())}
