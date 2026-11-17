"""tgb-rooms — абстрактная система комнат для Telegram-ботов на aiogram 3.

Вынесено из ``shelter-tgbot``: создание комнаты (название / тип / пароль),
вход по ключу, список активных комнат с просмотром, чёрный список и главное
сообщение комнаты с кнопками. Всё остальное (настройки, игра, боты, WS, БД)
кастомизируется через ``RoomsConfig`` и точки расширения.

Минимальное встраивание::

    from tgb_rooms import Rooms, RoomsConfig, MemoryRoomsBackend

    rooms = Rooms(backend=MemoryRoomsBackend(), config=RoomsConfig())
    dp.include_router(rooms.build_router())

ПУБЛИЧНЫЙ КОНТРАКТ
------------------
Встраивание делается **только через импорты из ``tgb_rooms``** — правится код
хоста, а не код библиотеки. Всё, что перечислено в ``__all__`` ниже,
стабильно: имена, сигнатуры и поведение сохраняются между минорными версиями.

- ``Rooms`` — фасад: ``build_router()``, ``entry_keyboard()``,
  ``resolve_principal()``, ``current_room()`` / ``get_room()``,
  ``render_room()``, ``lobby_keyboard()``, ``render_lobby()``,
  ``send_lobby()``, ``delete_lobby()``, ``refresh_lobbies()``,
  ``notify_room_changed()``, ``on_room_deleted()``, ``show_menu()``,
  ``clear_room()``, ``emit()``, ``text()``, ``error_text()``,
  ``attach_bot()``, ``settings_close_callback()``.
- ``RoomsConfig`` / ``Hooks`` — все настройки и хуки; новые поля только
  опциональные, значения по умолчанию = поведение исходного бота.
- ``RoomsBackend`` + коды ``ERR_*`` — контракт бэкенда; ``MemoryRoomsBackend``
  (автономный) и ``RestRoomsBackend`` + ``RestEndpoints`` (адаптер под REST).
- ``RoomsStorage`` / ``InMemoryRoomsStorage``, модели ``Room`` / ``Member`` /
  ``RoomDraft`` / ``RoomResult`` / ``Principal`` / ``Identity`` /
  ``UserBinding`` (+ ``ACTIVE`` / ``LEFT`` / ``KICKED``).
- ``CreateRoom`` / ``JoinRoom`` / ``RoomsBrowser`` (FSM), ``build_callbacks``,
  ``Keyboards``, ``UI``.
- ``DefaultTexts`` / ``TextProvider`` / ``make_texts``,
  ``format_lobby_message`` / ``format_blacklist_message`` /
  ``default_settings_lines`` / ``rooms_list_text``.
- Точки расширения: ``CreateStep`` / ``TextCreateStep`` /
  ``ChoiceCreateStep`` / ``StepOutcome`` / ``MaxPlayersStep``,
  ``LobbyButton``, ``SettingsExtension`` / ``SettingsContext``.

Внутреннее устройство (``handlers/_*.py``, ``core`` детали) менять не нужно;
но если понадобится сложная логика — файлы маленькие и самодостаточные,
см. карту в ``AGENTS.md``.
"""

from __future__ import annotations

from .backend import RoomsBackend
from .callbacks import build_callbacks
from .config import Hooks, RoomsConfig
from .core import Rooms
from .extensions import (
    ChoiceCreateStep,
    CreateStep,
    LobbyButton,
    MaxPlayersStep,
    SettingsContext,
    SettingsExtension,
    StepOutcome,
    TextCreateStep,
)
from .keyboards import Keyboards
from .memory_backend import MemoryRoomsBackend
from .messages import (
    default_settings_lines,
    format_blacklist_message,
    format_lobby_message,
    rooms_list_text,
)
from .models import (
    ACTIVE,
    KICKED,
    LEFT,
    Identity,
    Member,
    Principal,
    Room,
    RoomDraft,
    RoomResult,
    UserBinding,
)
from .rest_backend import RestEndpoints, RestRoomsBackend
from .states import CreateRoom, JoinRoom, RoomsBrowser
from .storage import InMemoryRoomsStorage, RoomsStorage
from .texts import DefaultTexts, TextProvider, make_texts
from .ui import UI

__version__ = "0.1.0"

__all__ = [
    # точка входа
    "Rooms",
    "RoomsConfig",
    "Hooks",
    # бэкенды
    "RoomsBackend",
    "MemoryRoomsBackend",
    "RestRoomsBackend",
    "RestEndpoints",
    # хранилище привязок
    "RoomsStorage",
    "InMemoryRoomsStorage",
    # модели
    "Room",
    "Member",
    "RoomDraft",
    "RoomResult",
    "Principal",
    "Identity",
    "UserBinding",
    "ACTIVE",
    "LEFT",
    "KICKED",
    # FSM / колбэки / UI
    "CreateRoom",
    "JoinRoom",
    "RoomsBrowser",
    "build_callbacks",
    "Keyboards",
    "UI",
    # тексты и сообщения
    "DefaultTexts",
    "TextProvider",
    "make_texts",
    "format_lobby_message",
    "format_blacklist_message",
    "default_settings_lines",
    "rooms_list_text",
    # точки расширения
    "CreateStep",
    "TextCreateStep",
    "ChoiceCreateStep",
    "StepOutcome",
    "MaxPlayersStep",
    "LobbyButton",
    "SettingsExtension",
    "SettingsContext",
    "__version__",
]
