"""Секция «чёрный список»: экран, кик/пардон кнопками и командами.

Исключение заносит ``player_id`` в ЧС, помилование убирает. Команды
``/kick <ник>`` и ``/pardon <ник>`` ищут участника по отображаемому имени
(кэш ``display_name`` + фолбэк на raw id). Логика дословно из ``handlers.py``.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from ..utils import decode_id, escape_html
from ._shared import (
    Flow,
    access_denied_text,
    chat_id,
    cleanup_blacklist_messages,
    lang,
    open_blacklist_view,
    principal,
    t,
)


def register_blacklist(f: Flow, router: Router) -> None:
    @router.callback_query(f.cb.Lobby.filter(F.action == "blacklist"))
    async def cb_open_blacklist(callback: CallbackQuery, **data) -> None:
        p = await principal(f, callback, data)
        room = await f.rooms.current_room(p)
        if room is None:
            await callback.answer(t(f, p, "GENERIC_ERROR"), show_alert=True)
            return
        if not await f.rooms.can_manage(room, p):
            await callback.answer(access_denied_text(f, p, room), show_alert=True)
            return
        await callback.answer()
        await open_blacklist_view(f, callback.bot, chat_id(callback), p, room)

    @router.callback_query(f.cb.Blacklist.filter(F.action == "back"))
    async def cb_blacklist_back(callback: CallbackQuery, **data) -> None:
        p = await principal(f, callback, data)
        await cleanup_blacklist_messages(f, callback.bot, p)
        room = await f.rooms.current_room(p)
        await f.storage.update_binding(p.user_id, settings_open=False)
        binding = await f.storage.get_binding(p.user_id)
        mid = binding.lobby_message_id if binding else None
        if mid is None and callback.message is not None:
            mid = callback.message.message_id
        if room is None or mid is None:
            await callback.answer(t(f, p, "GENERIC_ERROR"), show_alert=True)
            return
        await f.rooms.render_lobby(callback.bot, chat_id(callback), mid, p, room=room)
        await callback.answer()

    @router.callback_query(f.cb.Blacklist.filter(F.action == "add"))
    async def cb_blacklist_add(callback: CallbackQuery, **data) -> None:
        p = await principal(f, callback, data)
        room = await f.rooms.current_room(p)
        if room is None:
            await callback.answer(t(f, p, "GENERIC_ERROR"), show_alert=True)
            return
        if not await f.rooms.can_manage(room, p):
            await callback.answer(access_denied_text(f, p, room), show_alert=True)
            return
        await cleanup_blacklist_messages(f, callback.bot, p)
        fresh = await f.rooms.current_room(p) or room
        msg = await f.ui.send(
            callback.bot, p.user_id, t(f, p, "BLACKLIST_KICK_PROMPT"),
            reply_markup=f.kb.kick_choice(fresh, lang(f, p)),
        )
        await f.storage.update_binding(
            p.user_id,
            blacklist_view=True,
            blacklist_add_message_id=msg.message_id,
            blacklist_remove_message_id=None,
        )
        await callback.answer()

    @router.callback_query(f.cb.Blacklist.filter(F.action == "remove"))
    async def cb_blacklist_remove(callback: CallbackQuery, **data) -> None:
        p = await principal(f, callback, data)
        room = await f.rooms.current_room(p)
        if room is None:
            await callback.answer(t(f, p, "GENERIC_ERROR"), show_alert=True)
            return
        if not await f.rooms.can_manage(room, p):
            await callback.answer(access_denied_text(f, p, room), show_alert=True)
            return
        await cleanup_blacklist_messages(f, callback.bot, p)
        blacklist = await f.backend.get_blacklist(p, room.code)
        names: dict[str, str] = {}
        for entry in blacklist:
            name = await f.storage.get_display_name(entry)
            if name:
                names[entry] = name
        msg = await f.ui.send(
            callback.bot, p.user_id, t(f, p, "BLACKLIST_PARDON_PROMPT"),
            reply_markup=f.kb.pardon_choice(blacklist, lang(f, p), lambda e: names.get(e)),
        )
        await f.storage.update_binding(
            p.user_id,
            blacklist_remove_message_id=msg.message_id,
            blacklist_add_message_id=None,
        )
        await callback.answer()

    @router.callback_query(f.cb.Kick.filter())
    async def cb_kick_pick(callback: CallbackQuery, callback_data, **data) -> None:
        p = await principal(f, callback, data)
        room = await f.rooms.current_room(p)
        if room is None:
            await callback.answer(t(f, p, "GENERIC_ERROR"), show_alert=True)
            return
        if not await f.rooms.can_manage(room, p):
            await callback.answer(access_denied_text(f, p, room), show_alert=True)
            return
        target = decode_id(callback_data.target_id)
        if target == p.player_id:
            await callback.answer(t(f, p, "LOBBY_SELF_KICK"), show_alert=True)
            return
        result = await f.backend.kick(p, room.code, target)
        if result.error:
            reason = (result.message or "")[:150] or t(f, p, "GENERIC_ERROR")
            await callback.answer(t(f, p, "LOBBY_KICK_FAIL", reason=reason), show_alert=True)
            return
        binding = await f.storage.get_binding(p.user_id)
        if binding and binding.blacklist_add_message_id:
            await f.ui.try_delete(callback.bot, p.user_id, binding.blacklist_add_message_id)
        await f.storage.update_binding(p.user_id, blacklist_add_message_id=None)
        member = room.member(target)
        name = result.data.get("target_display_name") or (member.label if member else target)
        await f.storage.set_display_name(target, name)
        await callback.answer(t(f, p, "BLACKLIST_KICK_DONE"))
        await open_blacklist_view(f, callback.bot, chat_id(callback), p, room)
        await f.rooms.refresh_lobbies(room.code)
        await f.rooms.emit("on_member_kicked", p, room, target_player_id=target)
        await f.rooms.emit(
            "on_blacklist_changed", p, room, action="add", target_player_id=target
        )

    @router.callback_query(f.cb.Pardon.filter())
    async def cb_pardon_pick(callback: CallbackQuery, callback_data, **data) -> None:
        p = await principal(f, callback, data)
        room = await f.rooms.current_room(p)
        if room is None:
            await callback.answer(t(f, p, "GENERIC_ERROR"), show_alert=True)
            return
        if not await f.rooms.can_manage(room, p):
            await callback.answer(access_denied_text(f, p, room), show_alert=True)
            return
        target = decode_id(callback_data.target_id)
        result = await f.backend.pardon(p, room.code, target)
        if result.error:
            reason = (result.message or "")[:150] or t(f, p, "GENERIC_ERROR")
            await callback.answer(t(f, p, "LOBBY_KICK_FAIL", reason=reason), show_alert=True)
            return
        binding = await f.storage.get_binding(p.user_id)
        if binding and binding.blacklist_remove_message_id:
            await f.ui.try_delete(callback.bot, p.user_id, binding.blacklist_remove_message_id)
        await f.storage.update_binding(p.user_id, blacklist_remove_message_id=None)
        await callback.answer(t(f, p, "BLACKLIST_PARDON_DONE"))
        await open_blacklist_view(f, callback.bot, chat_id(callback), p, room)
        await f.rooms.emit("on_member_pardoned", p, room, target_player_id=target)
        await f.rooms.emit(
            "on_blacklist_changed", p, room, action="remove", target_player_id=target
        )

    @router.message(Command(commands=f.cfg.commands["kick"]))
    async def cmd_kick(
        message: Message, command: CommandObject | None = None, **data
    ) -> None:
        try:
            await message.delete()
        except Exception:
            pass
        p = await principal(f, message, data)
        room = await f.rooms.current_room(p)
        if room is None:
            await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "LOBBY_NOT_IN_ROOM"))
            return
        if not await f.rooms.can_manage(room, p):
            await f.ui.send_notice(message.bot, message.chat.id, access_denied_text(f, p, room))
            return
        nick = (command.args or "").strip() if command else ""
        if not nick:
            await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "CMD_KICK_USAGE"))
            return
        target = next(
            (m for m in room.active_members() if m.label.strip().lower() == nick.lower()),
            None,
        )
        if target is None:
            await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "LOBBY_PLAYER_NOT_FOUND"))
            return
        if target.player_id == p.player_id:
            await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "LOBBY_SELF_KICK"))
            return
        result = await f.backend.kick(p, room.code, target.player_id)
        if result.error:
            reason = (result.message or "")[:200] or t(f, p, "GENERIC_ERROR")
            await f.ui.send_notice(
                message.bot, message.chat.id, t(f, p, "LOBBY_KICK_FAIL", reason=reason)
            )
            return
        await f.storage.set_display_name(target.player_id, target.label)
        await f.ui.send_notice(
            message.bot, message.chat.id,
            t(f, p, "BLACKLIST_KICK_NOTIFY", nick=escape_html(target.label)),
        )
        await f.rooms.refresh_lobbies(room.code)
        await f.rooms.emit("on_member_kicked", p, room, target_player_id=target.player_id)
        await f.rooms.emit(
            "on_blacklist_changed", p, room, action="add", target_player_id=target.player_id
        )

    @router.message(Command(commands=f.cfg.commands["pardon"]))
    async def cmd_pardon(
        message: Message, command: CommandObject | None = None, **data
    ) -> None:
        try:
            await message.delete()
        except Exception:
            pass
        p = await principal(f, message, data)
        room = await f.rooms.current_room(p)
        if room is None:
            await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "LOBBY_NOT_IN_ROOM"))
            return
        if not await f.rooms.can_manage(room, p):
            await f.ui.send_notice(message.bot, message.chat.id, access_denied_text(f, p, room))
            return
        nick = (command.args or "").strip() if command else ""
        if not nick:
            await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "CMD_PARDON_USAGE"))
            return
        blacklist = await f.backend.get_blacklist(p, room.code)
        nick_l = nick.lower()
        target: str | None = None
        for entry in blacklist:
            cached = (await f.storage.get_display_name(entry) or "").lower()
            if cached == nick_l or entry.lower() == nick_l:
                target = entry
                break
        if target is None:
            await f.ui.send_notice(message.bot, message.chat.id, t(f, p, "LOBBY_BLACKLIST_NOT_FOUND"))
            return
        result = await f.backend.pardon(p, room.code, target)
        if result.error:
            reason = (result.message or "")[:200] or t(f, p, "GENERIC_ERROR")
            await f.ui.send_notice(
                message.bot, message.chat.id, t(f, p, "LOBBY_KICK_FAIL", reason=reason)
            )
            return
        label = await f.storage.get_display_name(target) or target
        await f.ui.send_notice(
            message.bot, message.chat.id,
            t(f, p, "BLACKLIST_PARDON_NOTIFY", nick=escape_html(label)),
        )
        await f.rooms.emit("on_member_pardoned", p, room, target_player_id=target)
        await f.rooms.emit(
            "on_blacklist_changed", p, room, action="remove", target_player_id=target
        )
