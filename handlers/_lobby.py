"""Секция «лобби»: выход, расформирование, настройки, кастомные кнопки.

Подтверждение выхода (по хуку ``needs_leave_confirm``), ``/disband`` +
``/confirm <CODE>``, открытие экрана настроек через ``SettingsExtension``,
кнопки из ``extra_lobby_buttons``. Логика дословно из ``handlers.py``.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..backend import ERR_FORBIDDEN, ERR_ROOM_NOT_FOUND
from ..extensions import SettingsContext
from ..utils import escape_html, maybe_await
from ._shared import (
    Flow,
    chat_id,
    err,
    lang,
    perform_leave,
    principal,
    t,
)


def register_lobby(f: Flow, router: Router) -> None:
    @router.message(Command(commands=f.cfg.commands["leave"]))
    async def cmd_leave(message: Message, state: FSMContext, **data) -> None:
        try:
            await message.delete()
        except Exception:
            pass
        await f.ui.drop_fsm_prompt(message.bot, message.chat.id, state)
        await state.clear()
        p = await principal(f, message, data)
        room = await f.rooms.current_room(p)
        if room is None:
            await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "LOBBY_NOT_IN_ROOM"))
            return
        if await f.rooms.needs_leave_confirm(room, p):
            await f.ui.send(
                message.bot, message.chat.id, t(f, p, "LOBBY_LEAVE_CONFIRM"),
                reply_markup=f.kb.leave_confirm(lang(f, p)),
            )
            return
        await perform_leave(f, message.bot, message.chat.id, p, room)

    @router.callback_query(f.cb.Lobby.filter(F.action == "leave"))
    async def cb_lobby_leave(callback: CallbackQuery, **data) -> None:
        p = await principal(f, callback, data)
        cid = chat_id(callback)
        room = await f.rooms.current_room(p)
        if room is None:
            await callback.answer(t(f, p, "LOBBY_NOT_IN_ROOM"), show_alert=True)
            return
        if await f.rooms.needs_leave_confirm(room, p):
            await f.ui.send(
                callback.bot, cid, t(f, p, "LOBBY_LEAVE_CONFIRM"),
                reply_markup=f.kb.leave_confirm(lang(f, p)),
            )
            await callback.answer()
            return
        await perform_leave(f, callback.bot, cid, p, room)
        await callback.answer()

    @router.callback_query(f.cb.Leave.filter())
    async def cb_leave_confirm(callback: CallbackQuery, callback_data, **data) -> None:
        p = await principal(f, callback, data)
        cid = chat_id(callback)
        mid = callback.message.message_id if callback.message is not None else None
        if callback_data.action == "stay":
            await f.ui.try_delete(callback.bot, cid, mid)
            await callback.answer()
            return
        room = await f.rooms.current_room(p)
        if room is None:
            await f.ui.try_delete(callback.bot, cid, mid)
            await callback.answer(t(f, p, "LOBBY_NOT_IN_ROOM"), show_alert=True)
            return
        await f.ui.try_delete(callback.bot, cid, mid)
        await perform_leave(f, callback.bot, cid, p, room)
        await callback.answer()

    @router.message(Command(commands=f.cfg.commands["disband"]))
    async def cmd_disband(message: Message, state: FSMContext, **data) -> None:
        try:
            await message.delete()
        except Exception:
            pass
        await f.ui.drop_fsm_prompt(message.bot, message.chat.id, state)
        await state.clear()
        p = await principal(f, message, data)
        code = p.room_code
        if not code:
            binding = await f.storage.get_binding(p.user_id)
            code = binding.room_code if binding else None
        if not code:
            await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "LOBBY_NOT_IN_ROOM"))
            return
        await f.ui.send(
            message.bot, message.chat.id,
            t(f, p, "LOBBY_DISBAND_CONFIRM", code=escape_html(code)),
        )

    @router.message(Command(commands=f.cfg.commands["confirm"]))
    async def cmd_confirm(
        message: Message, state: FSMContext, command: CommandObject | None = None, **data
    ) -> None:
        try:
            await message.delete()
        except Exception:
            pass
        await f.ui.drop_fsm_prompt(message.bot, message.chat.id, state)
        await state.clear()
        p = await principal(f, message, data)
        binding = await f.storage.get_binding(p.user_id)
        code = p.room_code or (binding.room_code if binding else None)
        if not code:
            await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "LOBBY_NOT_IN_ROOM"))
            return
        given = (command.args or "").strip().upper() if command else ""
        if given != code:
            await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "LOBBY_DISBAND_MISMATCH"))
            return
        result = await f.backend.disband_room(p, code)
        if result.error:
            if result.code == ERR_FORBIDDEN:
                await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "LOBBY_DISBAND_ONLY_OWNER"))
            elif result.code == ERR_ROOM_NOT_FOUND:
                await f.rooms.delete_lobby(message.bot, message.chat.id, p)
                await f.storage.clear_room(p.user_id)
                await f.rooms.show_menu(message.bot, message.chat.id, p)
            else:
                await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "GENERIC_ERROR"))
            return
        await f.rooms.delete_lobby(message.bot, message.chat.id, p)
        await f.storage.clear_room(p.user_id)
        await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "LOBBY_DISBAND_NOTIFY"))
        await f.rooms.show_menu(message.bot, message.chat.id, p)
        await f.rooms.emit("on_room_disbanded", p, None, code=code)
        await f.rooms.on_room_deleted(code, reason="disband", skip_user_id=p.user_id)

    @router.callback_query(f.cb.Lobby.filter(F.action == "settings"))
    async def cb_open_settings(callback: CallbackQuery, **data) -> None:
        p = await principal(f, callback, data)
        ext = f.cfg.settings_extension
        room = await f.rooms.current_room(p)
        if ext is None or room is None:
            await callback.answer(t(f, p, "PLACEHOLDER"))
            return
        available = (
            await maybe_await(ext.is_available(room, p))
            if hasattr(ext, "is_available")
            else await f.rooms.can_manage(room, p)
        )
        if not available:
            await callback.answer(t(f, p, "LOBBY_SETTINGS_ONLY_OWNER"), show_alert=True)
            return
        ctx = SettingsContext(
            rooms=f.rooms, callback=callback, room=room, principal=p, lang=lang(f, p)
        )
        await maybe_await(ext.open(ctx))
        await f.storage.update_binding(p.user_id, settings_open=True)
        await callback.answer()

    @router.callback_query(f.cb.Lobby.filter(F.action == "close_settings"))
    async def cb_close_settings(callback: CallbackQuery, **data) -> None:
        p = await principal(f, callback, data)
        cid = chat_id(callback)
        mid = callback.message.message_id if callback.message is not None else None
        room = await f.rooms.current_room(p)
        await f.storage.update_binding(p.user_id, settings_open=False)
        if room is None or mid is None:
            await f.ui.try_delete(callback.bot, cid, mid)
            await callback.answer(t(f, p, "GENERIC_ERROR"), show_alert=True)
            return
        await f.rooms.render_lobby(callback.bot, cid, mid, p, room=room)
        await callback.answer()

    @router.callback_query(f.cb.Extra.filter())
    async def cb_extra_button(callback: CallbackQuery, callback_data, **data) -> None:
        p = await principal(f, callback, data)
        index = int(callback_data.index)
        buttons = f.cfg.extra_lobby_buttons
        if not (0 <= index < len(buttons)):
            await callback.answer(t(f, p, "GENERIC_ERROR"))
            return
        button = buttons[index]
        if button.handler is None:
            await callback.answer(t(f, p, "PLACEHOLDER"))
            return
        room = await f.rooms.current_room(p)
        await maybe_await(button.handler(callback, room, p, f.rooms))
