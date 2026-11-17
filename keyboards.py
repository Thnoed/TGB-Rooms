"""Клавиатуры системы комнат.

Вынесено из ``app/keyboards/rooms.py``, ``app/keyboards/lobby.py``,
``app/keyboards/menus.py``. Все колбэки берутся из namespace ``cb``
(``build_callbacks``), все подписи — из ``TextProvider``; жёстко
зашитых ``app.*``-зависимостей нет.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from .models import Principal, Room
from .texts import TextProvider
from .utils import btn_text, encode_id


class Keyboards:
    """Фабрика клавиатур, привязанная к конкретному экземпляру ``Rooms``."""

    def __init__(
        self, cb: SimpleNamespace, texts: TextProvider, max_button_len: int = 60
    ) -> None:
        self.cb = cb
        self.texts = texts
        self.max_button_len = max_button_len

    def _text(self, _language: str, _text_key: str, **kwargs: Any) -> str:
        return self.texts.get(_language, _text_key, **kwargs)

    def _short(self, value: Any) -> str:
        return btn_text(str(value), self.max_button_len)

    # --- Вход в сценарии -----------------------------------------------------

    def cancel(self, lang: str) -> ReplyKeyboardMarkup:
        """Reply-клавиатура с кнопкой «Отмена» для FSM-диалогов."""
        builder = ReplyKeyboardBuilder()
        builder.button(text=self._text(lang, "CANCEL"))
        return builder.as_markup(resize_keyboard=True, input_field_placeholder="...")

    def entry(self, lang: str) -> InlineKeyboardMarkup:
        """Клавиатура «Создать / Найти / Список» — встраивается в меню хоста."""
        cb = self.cb
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=self._text(lang, "MAIN_CREATE"), callback_data=cb.Menu(action="create").pack()),
                    InlineKeyboardButton(text=self._text(lang, "MAIN_JOIN"), callback_data=cb.Menu(action="join").pack()),
                ],
                [InlineKeyboardButton(text=self._text(lang, "MAIN_ROOMS"), callback_data=cb.Menu(action="list").pack())],
            ]
        )

    def privacy(self, lang: str) -> InlineKeyboardMarkup:
        cb = self.cb
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=self._text(lang, "PRIVACY_PRIVATE"), callback_data=cb.Privacy(value="yes").pack()),
                    InlineKeyboardButton(text=self._text(lang, "PRIVACY_PUBLIC"), callback_data=cb.Privacy(value="no").pack()),
                ]
            ]
        )

    def join_method(self, lang: str) -> InlineKeyboardMarkup:
        cb = self.cb
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=self._text(lang, "JOIN_BY_CODE"), callback_data=cb.JoinMethod(method="code").pack())],
                [InlineKeyboardButton(text=self._text(lang, "JOIN_LIST"), callback_data=cb.JoinMethod(method="list").pack())],
                [InlineKeyboardButton(text=self._text(lang, "BACK"), callback_data=cb.JoinMethod(method="back").pack())],
            ]
        )

    def back_only(self, lang: str, callback_data: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=self._text(lang, "BACK"), callback_data=callback_data)]
            ]
        )

    # --- Список активных комнат ---------------------------------------------

    def room_label(self, room: Room, lang: str) -> str:
        owner = room.extra.get("owner_display")
        if not owner:
            member = room.member(room.owner_id)
            owner = member.label if member else room.owner_id
        cur = room.extra.get("players_count")
        if cur is None:
            cur = len(room.active_members())
        return self._text(
            lang,
            "ROOM_LIST_LABEL",
            owner=owner,
            name=room.name,
            cur=cur,
            max=room.max_players,
        )

    def rooms_list(
        self,
        items: list[Room],
        page: int,
        total: int,
        limit: int,
        lang: str,
    ) -> InlineKeyboardMarkup:
        cb = self.cb
        rows: list[list[InlineKeyboardButton]] = []
        for room in items:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=self._short(self.room_label(room, lang)),
                        callback_data=cb.List(action="pick", value=str(room.code)).pack(),
                    )
                ]
            )
        total_pages = max(1, (total + limit - 1) // limit)
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text=self._text(lang, "PREV"), callback_data=cb.List(action="prev").pack()))
        nav.append(
            InlineKeyboardButton(
                text=self._text(lang, "PAGINATION_PAGE", cur=page + 1, total=total_pages),
                callback_data=cb.List(action="page", value=str(page + 1)).pack(),
            )
        )
        if (page + 1) * limit < total:
            nav.append(InlineKeyboardButton(text=self._text(lang, "NEXT"), callback_data=cb.List(action="next").pack()))
        rows.append(nav)
        rows.append(
            [InlineKeyboardButton(text=self._text(lang, "BACK"), callback_data=cb.JoinMethod(method="back").pack())]
        )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    # --- Главное сообщение комнаты ------------------------------------------

    def lobby(
        self,
        room: Room,
        principal: Principal,
        lang: str,
        *,
        settings_label: str | None = None,
        extra_buttons: list[Any] | None = None,
        can_manage: bool = False,
    ) -> InlineKeyboardMarkup:
        """Кнопки лобби: настройки (хост), кастомные, ЧС (владелец), выход."""
        cb = self.cb
        rows: list[list[InlineKeyboardButton]] = []
        if settings_label:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=settings_label,
                        callback_data=cb.Lobby(action="settings").pack(),
                    )
                ]
            )
        # Индекс сохраняется по всем кнопкам, чтобы ExtraCB(index=i) был стабилен.
        for index, button in enumerate(extra_buttons or []):
            if not button.is_visible(room, principal):
                continue
            rows.append(
                [
                    InlineKeyboardButton(
                        text=self._short(button.label(room, principal, self.texts, lang)),
                        callback_data=cb.Extra(index=index).pack(),
                    )
                ]
            )
        if can_manage:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=self._text(lang, "LOBBY_BLACKLIST"),
                        callback_data=cb.Lobby(action="blacklist").pack(),
                    )
                ]
            )
        rows.append(
            [
                InlineKeyboardButton(
                    text=self._text(lang, "LOBBY_LEAVE"),
                    callback_data=cb.Lobby(action="leave").pack(),
                )
            ]
        )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def leave_confirm(self, lang: str) -> InlineKeyboardMarkup:
        cb = self.cb
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=self._text(lang, "LEAVE_STAY"), callback_data=cb.Leave(action="stay").pack()),
                    InlineKeyboardButton(text=self._text(lang, "LEAVE_GO"), callback_data=cb.Leave(action="confirm").pack()),
                ]
            ]
        )

    # --- Чёрный список -------------------------------------------------------

    def blacklist(self, lang: str) -> InlineKeyboardMarkup:
        cb = self.cb
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=self._text(lang, "BLACKLIST_ADD"), callback_data=cb.Blacklist(action="add").pack()),
                    InlineKeyboardButton(text=self._text(lang, "BLACKLIST_REMOVE"), callback_data=cb.Blacklist(action="remove").pack()),
                ],
                [InlineKeyboardButton(text=self._text(lang, "BACK"), callback_data=cb.Blacklist(action="back").pack())],
            ]
        )

    def kick_choice(self, room: Room, lang: str) -> InlineKeyboardMarkup:
        cb = self.cb
        rows: list[list[InlineKeyboardButton]] = []
        for member in room.active_members():
            if member.player_id == room.owner_id:
                continue
            rows.append(
                [
                    InlineKeyboardButton(
                        text=self._short(member.label),
                        callback_data=cb.Kick(target_id=encode_id(member.player_id)).pack(),
                    )
                ]
            )
        if not rows:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=self._text(lang, "KICK_EMPTY"),
                        callback_data=cb.Blacklist(action="back").pack(),
                    )
                ]
            )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def pardon_choice(
        self,
        blacklist: list[str],
        lang: str,
        display_name_resolver: Callable[[str], str | None] | None = None,
    ) -> InlineKeyboardMarkup:
        cb = self.cb
        rows: list[list[InlineKeyboardButton]] = []
        for entry in blacklist:
            name = None
            if display_name_resolver is not None:
                try:
                    name = display_name_resolver(entry)
                except Exception:
                    name = None
            rows.append(
                [
                    InlineKeyboardButton(
                        text=self._short(name or entry),
                        callback_data=cb.Pardon(target_id=encode_id(str(entry))).pack(),
                    )
                ]
            )
        if not rows:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=self._text(lang, "PARDON_EMPTY"),
                        callback_data=cb.Blacklist(action="back").pack(),
                    )
                ]
            )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    # --- Кастомные шаги создания ---------------------------------------------

    def create_choice_step(self, step: Any, index: int, lang: str) -> InlineKeyboardMarkup:
        cb = self.cb
        rows: list[list[InlineKeyboardButton]] = []
        for value, label in step.choices(self.texts, lang):
            rows.append(
                [
                    InlineKeyboardButton(
                        text=self._short(label),
                        callback_data=cb.CreateStep(index=index, value=value).pack(),
                    )
                ]
            )
        return InlineKeyboardMarkup(inline_keyboard=rows)
