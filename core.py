"""Ядро системы комнат: объект ``Rooms`` — единственная точка встраивания.

``Rooms`` связывает бэкенд, локальное хранилище привязок, тексты, UI,
клавиатуры и расширения. Хост создаёт один экземпляр, при необходимости
привязывает ``Bot`` и включает ``rooms.build_router()`` в свой Dispatcher.

Публичные методы (``refresh_lobbies``, ``notify_room_changed``,
``on_room_deleted``, ``send_lobby``, ``render_lobby``) нужны для интеграции
с внешними событиями: WebSocket, игра, админ-панель, таймеры.
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import BaseMiddleware, Router

from .backend import RoomsBackend
from .callbacks import build_callbacks
from .config import RoomsConfig
from .keyboards import Keyboards
from .memory_backend import MemoryRoomsBackend
from .messages import default_settings_lines, format_lobby_message
from .models import Identity, Principal, Room
from .storage import InMemoryRoomsStorage, RoomsStorage
from .texts import ERROR_TEXT_KEYS, make_texts
from .ui import UI
from .utils import maybe_await

logger = logging.getLogger(__name__)

#: Имя события ``notify_room_changed`` → дополнительный хук ``Hooks``.
EVENT_HOOK_NAMES: dict[str, str] = {
    "player_joined": "on_member_joined",
    "player_left": "on_member_left",
    "player_kicked": "on_member_kicked",
    "owner_changed": "on_owner_changed",
    "room_deleted": "on_room_deleted",
    "blacklist_changed": "on_blacklist_changed",
    "settings_updated": "on_settings_changed",
}


class _AttachBotMiddleware(BaseMiddleware):
    """Запоминает ``Bot`` из контекста aiogram для фоновых обновлений лобби."""

    def __init__(self, rooms: "Rooms") -> None:
        super().__init__()
        self._rooms = rooms

    async def __call__(self, handler, event, data: dict):
        bot = data.get("bot") or getattr(event, "bot", None)
        if bot is not None:
            self._rooms.attach_bot(bot)
        return await handler(event, data)


class Rooms:
    """Абстрактная система комнат, готовая к включению в любой aiogram-бот."""

    def __init__(
        self,
        backend: RoomsBackend | None = None,
        storage: RoomsStorage | None = None,
        config: RoomsConfig | None = None,
        *,
        bot: Any = None,
    ) -> None:
        self.config = config or RoomsConfig()
        self.backend = backend or MemoryRoomsBackend(
            code_length=self.config.code_length,
            code_factory=self.config.code_factory,
        )
        self.storage = storage or InMemoryRoomsStorage()
        self.cb = build_callbacks(self.config.callback_prefix)
        self.texts = make_texts(
            self.config.texts,
            self.config.text_overrides,
            self.config.default_language,
        )
        self.ui = UI(
            notice_lifetime=self.config.notice_lifetime,
            max_button_len=self.config.max_button_len,
            parse_mode=self.config.parse_mode,
        )
        self.kb = Keyboards(self.cb, self.texts, self.config.max_button_len)
        self._bot = bot if bot is not None else self.config.bot

    # --- базовое -------------------------------------------------------------

    def attach_bot(self, bot: Any) -> None:
        """Привязать ``aiogram.Bot`` (можно и в конструкторе, и после старта)."""
        self._bot = bot

    @property
    def bot(self) -> Any:
        return self._bot

    def text(self, _language: str, _text_key: str, **kwargs: Any) -> str:
        # Имена с подчёркиванием: плейсхолдер {key}/{lang} в тексте хоста
        # не должен конфликтовать с аргументами вызова.
        return self.texts.get(_language, _text_key, **kwargs)

    def error_text(self, _language: str, code: str) -> str:
        return self.text(_language, ERROR_TEXT_KEYS.get(code, "GENERIC_ERROR"))

    def entry_keyboard(self, lang: str | None = None):
        """Клавиатура «Создать / Найти / Список» для меню бота-хоста."""
        return self.kb.entry(lang or self.config.default_language)

    def settings_close_callback(self) -> str:
        """``callback_data`` кнопки «Назад в лобби» для расширения настроек."""
        return self.cb.Lobby(action="close_settings").pack()

    # --- идентичность и состояние -------------------------------------------

    async def resolve_principal(self, event: Any, data: dict | None = None) -> Principal:
        """Собрать ``Principal`` из события aiogram.

        По умолчанию ``player_id = str(telegram_id)``, имя — ``full_name``.
        Хост может подменить ``identity_resolver`` (вернуть ``Identity`` со
        своим ``player_id``/``token``) и ``language_resolver``.
        """
        data = data or {}
        tg_user = data.get("event_from_user") or getattr(event, "from_user", None)
        if tg_user is None:
            raise RuntimeError("tgb_rooms: не удалось определить пользователя события")
        user_id = int(tg_user.id)
        binding = await self.storage.get_binding(user_id)

        identity: Identity | None = None
        if self.config.identity_resolver is not None:
            identity = await maybe_await(self.config.identity_resolver(event, data))
        if identity is None:
            identity = Identity(
                user_id=user_id,
                player_id=str(user_id),
                display_name=getattr(tg_user, "full_name", "") or str(user_id),
                language=self.config.default_language,
            )

        lang = identity.language or self.config.default_language
        if self.config.language_resolver is not None:
            lang = (
                await maybe_await(self.config.language_resolver(user_id, data))
            ) or lang

        return Principal(
            user_id=user_id,
            player_id=identity.player_id or str(user_id),
            display_name=identity.display_name or "",
            token=identity.token,
            language=lang,
            room_code=binding.room_code if binding else None,
            extra=dict(identity.extra or {}),
        )

    async def current_room(self, principal: Principal, code: str | None = None) -> Room | None:
        """Комната пользователя (из ``Principal`` или из привязки)."""
        code = code or principal.room_code
        if not code:
            binding = await self.storage.get_binding(principal.user_id)
            code = binding.room_code if binding else None
        if not code:
            return None
        try:
            return await self.backend.get_room(principal, code)
        except Exception as exc:
            logger.warning("get_room(%s): %s", code, exc)
            return None

    # псевдоним для расширений
    get_room = current_room

    async def _room_by_code(self, code: str) -> Room | None:
        """Снимок комнаты токеном любого её участника (как ``refresh_room_lobbies``)."""
        for binding in await self.storage.get_users_in_room(code):
            try:
                room = await self.backend.get_room(binding.as_principal(), code)
            except Exception:
                continue
            if room is not None:
                return room
        return None

    async def can_manage(self, room: Room, principal: Principal) -> bool:
        """Можно ли управлять ЧС/настройками (по умолчанию: владелец + waiting)."""
        if self.config.can_manage is not None:
            return bool(await maybe_await(self.config.can_manage(room, principal)))
        return room.is_owner(principal.player_id) and room.status in self.config.editable_statuses

    async def needs_leave_confirm(self, room: Room, principal: Principal) -> bool:
        """Нужен ли экран подтверждения выхода (в исходном боте — во время игры)."""
        if self.config.needs_leave_confirm is not None:
            return bool(await maybe_await(self.config.needs_leave_confirm(room, principal)))
        return False

    # --- рендеринг главного сообщения ---------------------------------------

    async def render_room(
        self,
        room: Room,
        principal: Principal,
        lang: str | None = None,
        *,
        settings_lines: list[str] | None = None,
    ) -> str:
        """Текст главного сообщения комнаты (можно заменить рендерером хоста)."""
        lang = lang or principal.language or self.config.default_language
        if self.config.room_info_renderer is not None:
            return str(
                await maybe_await(
                    self.config.room_info_renderer(room, principal, self, lang)
                )
            )
        if settings_lines is None:
            if self.config.settings_summary is not None:
                settings_lines = list(
                    await maybe_await(self.config.settings_summary(room, principal, self))
                    or []
                )
            else:
                settings_lines = default_settings_lines(room, self.texts, lang)
        names: dict[str, str] = {}
        for member in room.members:
            cached = await self.storage.get_display_name(member.player_id)
            if cached:
                names[member.player_id] = cached
        return format_lobby_message(
            room,
            principal,
            self.texts,
            lang,
            settings_lines=settings_lines,
            display_name_resolver=lambda pid: names.get(pid),
        )

    async def lobby_keyboard(self, room: Room, principal: Principal, lang: str | None = None):
        """Клавиатура главного сообщения (настройки + кастомные + ЧС + выход)."""
        lang = lang or principal.language or self.config.default_language
        settings_label: str | None = None
        ext = self.config.settings_extension
        if ext is not None:
            try:
                settings_label = ext.button_text(room, principal, self.texts, lang)
            except Exception as exc:
                logger.debug("settings_extension.button_text: %s", exc)
                settings_label = None
        can_manage = await self.can_manage(room, principal)
        return self.kb.lobby(
            room,
            principal,
            lang,
            settings_label=settings_label,
            extra_buttons=self.config.extra_lobby_buttons,
            can_manage=can_manage,
        )

    async def render_lobby(
        self,
        bot: Any,
        chat_id: int,
        message_id: int,
        principal: Principal,
        room: Room | None = None,
    ) -> None:
        """Перерисовать главное сообщение комнаты (редактированием)."""
        room = room or await self.current_room(principal)
        if room is None:
            return
        lang = principal.language or self.config.default_language
        text = await self.render_room(room, principal, lang)
        markup = await self.lobby_keyboard(room, principal, lang)
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=markup,
                parse_mode=self.config.parse_mode,
            )
        except Exception as exc:
            if not self.ui.is_not_modified(exc):
                logger.warning("render_lobby(%s): %s", chat_id, exc)

    async def send_lobby(
        self, bot: Any, chat_id: int, principal: Principal, room: Room
    ) -> Any:
        """Отправить новое главное сообщение и запомнить его id."""
        lang = principal.language or self.config.default_language
        text = await self.render_room(room, principal, lang)
        markup = await self.lobby_keyboard(room, principal, lang)
        msg = await self.ui.send(bot, chat_id, text, reply_markup=markup)
        await self.storage.update_binding(
            principal.user_id,
            room_code=room.code,
            lobby_message_id=msg.message_id,
            player_id=principal.player_id,
            display_name=principal.display_name,
            token=principal.token,
            language=lang,
            blacklist_view=False,
            blacklist_add_message_id=None,
            blacklist_remove_message_id=None,
            settings_open=False,
        )
        for member in room.members:
            await self.storage.set_display_name(member.player_id, member.label)
        return msg

    async def delete_lobby(self, bot: Any, chat_id: int, principal: Principal) -> None:
        binding = await self.storage.get_binding(principal.user_id)
        if binding and binding.lobby_message_id:
            await self.ui.try_delete(bot, chat_id, binding.lobby_message_id)
            await self.storage.update_binding(principal.user_id, lobby_message_id=None)

    async def refresh_lobbies(self, code: str) -> None:
        """Обновить главное сообщение у всех участников комнаты.

        Вызывайте из обработчиков WebSocket / игры / админ-панели после любого
        изменения состава или состояния комнаты (порт ``refresh_room_lobbies``).
        """
        bot = self._bot
        if bot is None:
            return
        room = await self._room_by_code(code)
        if room is None:
            return
        for binding in await self.storage.get_users_in_room(code):
            if binding.lobby_message_id is None:
                continue
            # Не портим открытые экраны ЧС / настроек.
            if binding.blacklist_view or binding.settings_open:
                continue
            await self.render_lobby(
                bot,
                binding.user_id,
                binding.lobby_message_id,
                binding.as_principal(),
                room=room,
            )

    # --- меню и привязки -----------------------------------------------------

    async def show_menu(self, bot: Any, chat_id: int, principal: Principal) -> Any:
        """Показать меню после отмены/выхода. Переопределяется ``on_show_menu``."""
        if self.config.on_show_menu is not None:
            return await maybe_await(
                self.config.on_show_menu(bot, chat_id, principal, self)
            )
        binding = await self.storage.get_binding(principal.user_id)
        if binding and binding.menu_message_id:
            await self.ui.try_delete(bot, chat_id, binding.menu_message_id)
        await self.ui.clear_reply_keyboard(bot, chat_id)
        lang = principal.language or self.config.default_language
        msg = await self.ui.send(
            bot, chat_id, self.text(lang, "MENU_TITLE"), reply_markup=self.kb.entry(lang)
        )
        await self.storage.update_binding(principal.user_id, menu_message_id=msg.message_id)
        return msg

    async def clear_room(self, user_id: int) -> None:
        await self.storage.clear_room(user_id)

    # --- хуки и внешние события ---------------------------------------------

    async def emit(
        self,
        hook_name: str,
        principal: Principal | None,
        room: Room | None,
        **payload: Any,
    ) -> None:
        hook = getattr(self.config.hooks, hook_name, None)
        if hook is None:
            return
        # Ключи, зарезервированные под служебные kwargs хука, не должны
        # ломать вызов, если в payload события пришло одноимённое поле.
        reserved = {"rooms", "principal", "room", "hook", "error", "hook_name"}
        clean = {k: v for k, v in payload.items() if k not in reserved}
        try:
            await maybe_await(
                hook(rooms=self, principal=principal, room=room, **clean)
            )
        except Exception as exc:
            logger.exception("tgb_rooms: хук %s упал: %s", hook_name, exc)
            if hook_name != "on_error" and self.config.hooks.on_error is not None:
                try:
                    await maybe_await(
                        self.config.hooks.on_error(
                            rooms=self,
                            principal=principal,
                            room=room,
                            hook=hook_name,
                            error=exc,
                            **clean,
                        )
                    )
                except Exception:
                    logger.exception("tgb_rooms: хук on_error тоже упал")

    async def notify_room_changed(
        self,
        code: str,
        event: str,
        *,
        refresh: bool = True,
        notify: bool | None = None,
        **payload: Any,
    ) -> None:
        """Универсальная точка для внешних событий (WS/игра/админка).

        Рассылает хуки, при ``notify=True`` — временные уведомления участникам
        (текст берётся из ``event_text_keys``), затем обновляет лобби.
        """
        room = await self._room_by_code(code)
        event_payload = dict(payload)
        event_payload["code"] = code
        event_payload["event"] = event
        await self.emit("on_room_changed", None, room, **event_payload)
        hook_name = EVENT_HOOK_NAMES.get(event)
        if hook_name:
            await self.emit(hook_name, None, room, **event_payload)
        if notify is None:
            notify = self.config.notify_events
        if notify and self._bot is not None:
            key = self.config.event_text_keys.get(event)
            if key:
                for binding in await self.storage.get_users_in_room(code):
                    try:
                        await self.ui.send_notice(
                            self._bot,
                            binding.user_id,
                            self.text(binding.language, key, **payload),
                        )
                    except Exception as exc:
                        logger.debug("notify_room_changed(%s): %s", binding.user_id, exc)
        if refresh and room is not None:
            await self.refresh_lobbies(code)

    async def on_room_deleted(
        self, code: str, *, reason: str = "deleted", skip_user_id: int | None = None
    ) -> None:
        """Комната удалена на сервере: снять привязки, уведомить, показать меню.

        Используйте вместо ``notify_room_changed(..., event="room_deleted")``,
        когда комнаты уже физически нет (порт ``_on_room_deleted`` из WS).
        """
        bot = self._bot
        key = self.config.event_text_keys.get("room_deleted")
        for binding in await self.storage.get_users_in_room(code):
            if skip_user_id is not None and binding.user_id == skip_user_id:
                continue
            await self.storage.clear_room(binding.user_id)
            if bot is not None:
                try:
                    if key:
                        await self.ui.send_notice(
                            bot, binding.user_id, self.text(binding.language, key)
                        )
                    await self.show_menu(bot, binding.user_id, binding.as_principal())
                except Exception as exc:
                    logger.debug("on_room_deleted(%s): %s", binding.user_id, exc)
        await self.emit("on_room_deleted", None, None, code=code, reason=reason)

    # --- сборка роутера ------------------------------------------------------

    def build_router(self) -> Router:
        """Собрать aiogram ``Router`` со всеми сценариями системы комнат."""
        router = Router(name=f"tgb_rooms_{self.config.callback_prefix}")
        router.message.middleware(_AttachBotMiddleware(self))
        router.callback_query.middleware(_AttachBotMiddleware(self))

        from .handlers import register_handlers

        register_handlers(self, router)

        ext = self.config.settings_extension
        if ext is not None:
            builder = getattr(ext, "build_router", None)
            if builder is not None:
                child = builder(self)
                if child is not None:
                    router.include_router(child)
        for extra in self.config.extra_routers:
            router.include_router(extra)
        return router
