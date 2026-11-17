"""Секция «создание комнаты»: команды, кнопки меню, FSM мастера.

Базовые шаги: ``name → privacy → password``; дальше — кастомные шаги из
``RoomsConfig.create_steps`` (индекс шага лежит в FSM-данных, все шаги делят
состояние ``CreateRoom.extra``). Логика дословно из ``handlers.py``.
"""

from __future__ import annotations

from dataclasses import asdict

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..models import RoomDraft
from ..states import CreateRoom
from ..utils import maybe_await
from ._shared import (
    Flow,
    advance_create,
    attempt_join,
    chat_id,
    ensure_free,
    lang,
    open_join_method,
    open_rooms_list,
    principal,
    start_create,
    t,
)


def register_create(f: Flow, router: Router) -> None:
    @router.message(Command(commands=f.cfg.commands["create"]))
    async def cmd_create(message: Message, state: FSMContext, **data) -> None:
        p = await principal(f, message, data)
        if not await ensure_free(f, p, message):
            return
        try:
            await message.delete()
        except Exception:
            pass
        await start_create(f, message.bot, message.chat.id, state, p)

    @router.message(Command(commands=f.cfg.commands["join"]))
    async def cmd_join(
        message: Message, state: FSMContext, command: CommandObject | None = None, **data
    ) -> None:
        p = await principal(f, message, data)
        if not await ensure_free(f, p, message):
            return
        try:
            await message.delete()
        except Exception:
            pass
        code = (command.args or "").strip().upper() if command else ""
        if code:
            await state.update_data(code=code)
            await attempt_join(f, message.bot, message.chat.id, state, p, code)
        else:
            await open_join_method(f, message.bot, message.chat.id, state, p)

    @router.message(Command(commands=f.cfg.commands["rooms"]))
    async def cmd_rooms(message: Message, state: FSMContext, **data) -> None:
        p = await principal(f, message, data)
        if not await ensure_free(f, p, message):
            return
        try:
            await message.delete()
        except Exception:
            pass
        await open_rooms_list(f, message.bot, message.chat.id, state, p, 0)

    @router.callback_query(f.cb.Menu.filter(F.action == "create"))
    async def cb_create(callback: CallbackQuery, state: FSMContext, **data) -> None:
        p = await principal(f, callback, data)
        if not await ensure_free(f, p, callback):
            return
        cid = chat_id(callback)
        if f.cfg.delete_menu_on_action and callback.message is not None:
            await f.ui.try_delete(callback.bot, cid, callback.message.message_id)
            await f.storage.update_binding(p.user_id, menu_message_id=None)
        await start_create(f, callback.bot, cid, state, p)
        await callback.answer()

    @router.callback_query(f.cb.Menu.filter(F.action == "join"))
    async def cb_join(callback: CallbackQuery, state: FSMContext, **data) -> None:
        p = await principal(f, callback, data)
        if not await ensure_free(f, p, callback):
            return
        cid = chat_id(callback)
        if f.cfg.delete_menu_on_action and callback.message is not None:
            await f.ui.try_delete(callback.bot, cid, callback.message.message_id)
            await f.storage.update_binding(p.user_id, menu_message_id=None)
        await open_join_method(f, callback.bot, cid, state, p)
        await callback.answer()

    @router.callback_query(f.cb.Menu.filter(F.action == "list"))
    async def cb_rooms(callback: CallbackQuery, state: FSMContext, **data) -> None:
        p = await principal(f, callback, data)
        if not await ensure_free(f, p, callback):
            return
        cid = chat_id(callback)
        if f.cfg.delete_menu_on_action and callback.message is not None:
            await f.ui.try_delete(callback.bot, cid, callback.message.message_id)
            await f.storage.update_binding(p.user_id, menu_message_id=None)
        await open_rooms_list(f, callback.bot, cid, state, p, 0)
        await callback.answer()

    @router.message(CreateRoom.name)
    async def process_room_name(message: Message, state: FSMContext, **data) -> None:
        try:
            await message.delete()
        except Exception:
            pass
        p = await principal(f, message, data)
        data_fsm = await state.get_data()
        draft = RoomDraft(**(data_fsm.get("draft") or asdict(RoomDraft())))
        name = (message.text or "").strip()
        if not (f.cfg.name_min_len <= len(name) <= f.cfg.name_max_len):
            await f.ui.fsm_ask(
                message.bot, message.chat.id, state, t(f, p, "CREATE_NAME_ERROR"),
                reply_markup=f.kb.cancel(lang(f, p)),
            )
            return
        draft.name = name
        draft.is_private = False
        draft.password = None
        await state.update_data(draft=asdict(draft))
        await f.ui.fsm_ask(
            message.bot, message.chat.id, state, t(f, p, "CREATE_PRIVACY_PROMPT"),
            reply_markup=f.kb.privacy(lang(f, p)),
        )
        await state.set_state(CreateRoom.privacy)

    @router.callback_query(CreateRoom.privacy, f.cb.Privacy.filter())
    async def process_privacy(
        callback: CallbackQuery, callback_data, state: FSMContext, **data
    ) -> None:
        p = await principal(f, callback, data)
        cid = chat_id(callback)
        if callback.message is not None:
            await f.ui.try_delete(callback.bot, cid, callback.message.message_id)
        await state.update_data(prompt_mid=None)
        data_fsm = await state.get_data()
        draft = RoomDraft(**(data_fsm.get("draft") or asdict(RoomDraft())))
        is_private = callback_data.value == "yes"
        draft.is_private = is_private
        await state.update_data(draft=asdict(draft))
        await callback.answer()
        if is_private:
            await f.ui.fsm_ask(
                callback.bot, cid, state, t(f, p, "CREATE_PASSWORD_PROMPT"),
                reply_markup=f.kb.cancel(lang(f, p)),
            )
            await state.set_state(CreateRoom.password)
        else:
            await advance_create(f, callback.bot, cid, state, p, 0)

    @router.message(CreateRoom.password)
    async def process_room_password(message: Message, state: FSMContext, **data) -> None:
        try:
            await message.delete()
        except Exception:
            pass
        p = await principal(f, message, data)
        password = (message.text or "").strip()
        if not (f.cfg.password_min_len <= len(password) <= f.cfg.password_max_len):
            await f.ui.fsm_ask(
                message.bot, message.chat.id, state, t(f, p, "CREATE_PASSWORD_ERROR"),
                reply_markup=f.kb.cancel(lang(f, p)),
            )
            return
        data_fsm = await state.get_data()
        draft = RoomDraft(**(data_fsm.get("draft") or asdict(RoomDraft())))
        draft.password = password
        draft.is_private = True
        await state.update_data(draft=asdict(draft))
        await advance_create(f, message.bot, message.chat.id, state, p, 0)

    @router.message(CreateRoom.extra)
    async def process_create_extra(message: Message, state: FSMContext, **data) -> None:
        try:
            await message.delete()
        except Exception:
            pass
        p = await principal(f, message, data)
        fsm = await state.get_data()
        index = int(fsm.get("step_index", 0))
        steps = f.cfg.create_steps
        if index >= len(steps) or getattr(steps[index], "mode", "text") != "text":
            return
        step = steps[index]
        outcome = await maybe_await(step.validate(message.text or "", p, f.texts, lang(f, p)))
        if not outcome.ok:
            key = outcome.error_key or "GENERIC_ERROR"
            await f.ui.fsm_ask(
                message.bot, message.chat.id, state,
                f.texts.get(lang(f, p), key, **(outcome.error_kwargs or {})),
                reply_markup=f.kb.cancel(lang(f, p)),
            )
            return
        draft = RoomDraft(**(fsm.get("draft") or asdict(RoomDraft())))
        step.apply(draft, outcome.value)
        await state.update_data(draft=asdict(draft))
        await advance_create(f, message.bot, message.chat.id, state, p, index + 1)

    @router.callback_query(CreateRoom.extra, f.cb.CreateStep.filter())
    async def process_create_extra_choice(
        callback: CallbackQuery, callback_data, state: FSMContext, **data
    ) -> None:
        p = await principal(f, callback, data)
        cid = chat_id(callback)
        fsm = await state.get_data()
        index = int(fsm.get("step_index", 0))
        steps = f.cfg.create_steps
        if callback_data.index != index or index >= len(steps):
            await callback.answer()
            return
        if callback.message is not None:
            await f.ui.try_delete(callback.bot, cid, callback.message.message_id)
        await state.update_data(prompt_mid=None)
        draft = RoomDraft(**(fsm.get("draft") or asdict(RoomDraft())))
        steps[index].apply(draft, callback_data.value)
        await state.update_data(draft=asdict(draft))
        await callback.answer()
        await advance_create(f, callback.bot, cid, state, p, index + 1)
