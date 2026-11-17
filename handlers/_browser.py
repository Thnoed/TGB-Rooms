"""Секция «вход в комнату»: способ входа, список комнат, код, пароль.

Выбор «по коду / из списка», постраничный просмотр активных комнат
(``prev/next``, переход на страницу по номеру, выбор кнопкой), запрос пароля
для приватных комнат с проверкой чёрного списка. Логика дословно из
``handlers.py``.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..messages import rooms_list_text
from ..states import JoinRoom, RoomsBrowser
from ._shared import (
    Flow,
    attempt_join,
    chat_id,
    fetch_page,
    lang,
    open_join_method,
    open_rooms_list,
    principal,
    t,
)

logger = logging.getLogger(__name__)


def register_browser(f: Flow, router: Router) -> None:
    @router.callback_query(JoinRoom.method, f.cb.JoinMethod.filter(F.method == "code"))
    async def cb_join_by_code(callback: CallbackQuery, state: FSMContext, **data) -> None:
        p = await principal(f, callback, data)
        cid = chat_id(callback)
        if callback.message is not None:
            await f.ui.try_delete(callback.bot, cid, callback.message.message_id)
        await state.update_data(prompt_mid=None)
        await f.ui.fsm_ask(
            callback.bot, cid, state, t(f, p, "JOIN_CODE_PROMPT"),
            reply_markup=f.kb.cancel(lang(f, p)),
        )
        await state.set_state(JoinRoom.code)
        await callback.answer()

    @router.callback_query(JoinRoom.method, f.cb.JoinMethod.filter(F.method == "list"))
    async def cb_join_list(callback: CallbackQuery, state: FSMContext, **data) -> None:
        p = await principal(f, callback, data)
        await open_rooms_list(f, callback.bot, chat_id(callback), state, p, 0)
        await callback.answer()

    @router.callback_query(JoinRoom.method, f.cb.JoinMethod.filter(F.method == "back"))
    async def cb_join_method_back(callback: CallbackQuery, state: FSMContext, **data) -> None:
        await f.ui.drop_fsm_prompt(callback.bot, chat_id(callback), state)
        await state.clear()
        p = await principal(f, callback, data)
        await f.rooms.show_menu(callback.bot, chat_id(callback), p)
        await callback.answer()

    @router.callback_query(RoomsBrowser.page, f.cb.JoinMethod.filter(F.method == "back"))
    @router.callback_query(RoomsBrowser.page_input, f.cb.JoinMethod.filter(F.method == "back"))
    async def cb_rooms_list_back_to_join(
        callback: CallbackQuery, state: FSMContext, **data
    ) -> None:
        await f.ui.drop_fsm_prompt(callback.bot, chat_id(callback), state)
        p = await principal(f, callback, data)
        await open_join_method(f, callback.bot, chat_id(callback), state, p)
        await callback.answer()

    @router.callback_query(f.cb.List.filter())
    async def cb_rooms_list_action(
        callback: CallbackQuery, callback_data, state: FSMContext, **data
    ) -> None:
        p = await principal(f, callback, data)
        cid = chat_id(callback)
        limit = f.cfg.rooms_page_size
        action = callback_data.action

        if action == "pick":
            code = (callback_data.value or "").strip().upper()
            await attempt_join(
                f, callback.bot, cid, state, p, code, answer=callback.answer
            )
            return
        if action == "page":
            if callback.message is not None:
                await f.ui.try_delete(callback.bot, cid, callback.message.message_id)
            await f.ui.fsm_ask(
                callback.bot, cid, state, t(f, p, "JOIN_PAGE_PROMPT"),
                reply_markup=f.kb.cancel(lang(f, p)),
            )
            await state.set_state(RoomsBrowser.page_input)
            await callback.answer()
            return
        if action not in ("prev", "next"):
            await callback.answer()
            return
        fsm = await state.get_data()
        current = int(fsm.get("rooms_page", 0))
        page = max(0, current - 1) if action == "prev" else current + 1
        items, total = await fetch_page(f, page, p)
        if not items and total > 0:
            page = max(0, min(page, (total - 1) // limit))
            items, total = await fetch_page(f, page, p)
        await state.update_data(rooms_page=page)
        text = rooms_list_text(items, page, total, limit, f.texts, lang(f, p))
        markup = f.kb.rooms_list(items, page, total, limit, lang(f, p))
        try:
            await callback.message.edit_text(
                text, reply_markup=markup, parse_mode=f.cfg.parse_mode
            )
        except Exception as exc:
            logger.debug("rooms list edit: %s", exc)
            await f.ui.send(callback.bot, cid, text, reply_markup=markup)
        await callback.answer()

    @router.message(RoomsBrowser.page_input)
    async def process_rooms_page_input(message: Message, state: FSMContext, **data) -> None:
        try:
            await message.delete()
        except Exception:
            pass
        p = await principal(f, message, data)
        limit = f.cfg.rooms_page_size
        try:
            page = max(0, int((message.text or "").strip()) - 1)
        except ValueError:
            await f.ui.fsm_ask(
                message.bot, message.chat.id, state, t(f, p, "JOIN_PAGE_NAN"),
                reply_markup=f.kb.cancel(lang(f, p)),
            )
            return
        items, total = await fetch_page(f, page, p)
        if not items and total == 0:
            await f.ui.drop_fsm_prompt(message.bot, message.chat.id, state)
            await state.clear()
            await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "JOIN_NO_ROOMS"))
            return
        if not items:
            await f.ui.fsm_ask(
                message.bot, message.chat.id, state,
                t(f, p, "JOIN_PAGE_EMPTY", page=page + 1, total=((total - 1) // limit) + 1),
                reply_markup=f.kb.cancel(lang(f, p)),
            )
            return
        await f.ui.drop_fsm_prompt(message.bot, message.chat.id, state)
        await state.update_data(rooms_page=page)
        text = rooms_list_text(items, page, total, limit, f.texts, lang(f, p))
        markup = f.kb.rooms_list(items, page, total, limit, lang(f, p))
        msg = await f.ui.send(message.bot, message.chat.id, text, reply_markup=markup)
        await state.update_data(prompt_mid=msg.message_id)
        await state.set_state(RoomsBrowser.page)

    @router.message(JoinRoom.code)
    async def process_join_code(message: Message, state: FSMContext, **data) -> None:
        try:
            await message.delete()
        except Exception:
            pass
        p = await principal(f, message, data)
        code = (message.text or "").strip().upper()
        if not code:
            await f.ui.fsm_ask(
                message.bot, message.chat.id, state, t(f, p, "JOIN_CODE_EMPTY"),
                reply_markup=f.kb.cancel(lang(f, p)),
            )
            return
        await state.update_data(code=code)
        await attempt_join(f, message.bot, message.chat.id, state, p, code)

    @router.message(JoinRoom.password)
    async def process_join_password(message: Message, state: FSMContext, **data) -> None:
        try:
            await message.delete()
        except Exception:
            pass
        p = await principal(f, message, data)
        password = (message.text or "").strip()
        fsm = await state.get_data()
        code = fsm.get("code")
        if not code:
            await f.ui.drop_fsm_prompt(message.bot, message.chat.id, state)
            await state.clear()
            await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "GENERIC_ERROR"))
            await f.rooms.show_menu(message.bot, message.chat.id, p)
            return
        await attempt_join(
            f, message.bot, message.chat.id, state, p, code,
            password=password, retry_password=True,
        )
