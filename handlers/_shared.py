"""Общий контекст и хелперы сценариев системы комнат.

``Flow`` заменяет замыкания исходного ``register_handlers``: все секции
(``_create``, ``_browser``, ``_lobby``, ``_blacklist``) получают один и тот
же объект и не дублируют доступ к ``Rooms``. Поведение хелперов — дословно
из ``handlers.py`` (отмена, сборка черновика, вход, выход, экран ЧС).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..backend import ERR_ACCESS_DENIED, ERR_ALREADY_IN_ROOM
from ..models import Room, RoomDraft
from ..messages import format_blacklist_message, rooms_list_text
from ..states import CreateRoom, JoinRoom, RoomsBrowser
from ..texts import ERROR_TEXT_KEYS

logger = logging.getLogger(__name__)


@dataclass
class Flow:
    """Всё, что нужно хендлерам: ссылки на ``Rooms`` и его части."""

    rooms: Any
    cfg: Any
    cb: Any
    ui: Any
    kb: Any
    texts: Any
    backend: Any
    storage: Any


def lang(f: Flow, p) -> str:
    return p.language or f.cfg.default_language


def t(f: Flow, p, key: str, **kwargs) -> str:
    return f.rooms.text(lang(f, p), key, **kwargs)


def err(f: Flow, p, code: str) -> str:
    return f.rooms.error_text(lang(f, p), code)


def chat_id(event) -> int:
    if isinstance(event, CallbackQuery) and event.message is not None:
        return event.message.chat.id
    if isinstance(event, Message):
        return event.chat.id
    return event.from_user.id


async def principal(f: Flow, event, data: dict):
    return await f.rooms.resolve_principal(event, data)


async def ensure_free(f: Flow, p, event) -> bool:
    binding = await f.storage.get_binding(p.user_id)
    if binding and binding.room_code:
        text = t(f, p, "LOBBY_ALREADY_IN_ROOM")
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await f.ui.send_notice(event.bot, chat_id(event), text)
        return False
    return True


def access_denied_text(f: Flow, p, room: Room) -> str:
    if not room.is_owner(p.player_id):
        return t(f, p, "LOBBY_BLACKLIST_ONLY_OWNER")
    return t(f, p, "LOBBY_BLACKLIST_ONLY_WAITING")


async def open_join_method(f: Flow, bot, chat_id_: int, state: FSMContext, p) -> None:
    await f.ui.fsm_ask(
        bot, chat_id_, state, t(f, p, "JOIN_METHOD_PROMPT"),
        reply_markup=f.kb.join_method(lang(f, p)),
    )
    await state.set_state(JoinRoom.method)


async def start_create(f: Flow, bot, chat_id_: int, state: FSMContext, p) -> None:
    await state.clear()
    await state.update_data(draft=asdict(RoomDraft(max_players=f.cfg.default_max_players)))
    await f.ui.fsm_ask(
        bot, chat_id_, state, t(f, p, "CREATE_NAME_PROMPT"),
        reply_markup=f.kb.cancel(lang(f, p)),
    )
    await state.set_state(CreateRoom.name)


async def finish_create(f: Flow, bot, chat_id_: int, state: FSMContext, p) -> None:
    data = await state.get_data()
    draft = RoomDraft(**(data.get("draft") or asdict(RoomDraft())))
    await f.ui.drop_fsm_prompt(bot, chat_id_, state)
    await state.clear()
    result = await f.backend.create_room(p, draft)
    if result.error or result.room is None:
        key = (
            "CREATE_ALREADY_IN_ROOM"
            if result.code == ERR_ALREADY_IN_ROOM
            else ERROR_TEXT_KEYS.get(result.code, "GENERIC_ERROR")
        )
        await f.ui.send_notice(bot, chat_id_, t(f, p, key))
        await f.rooms.show_menu(bot, chat_id_, p)
        await f.rooms.emit("on_error", p, None, operation="create_room", code=result.code)
        return
    room = result.room
    p.room_code = room.code
    await f.storage.update_binding(
        p.user_id,
        room_code=room.code,
        lobby_message_id=None,
        player_id=p.player_id,
        display_name=p.display_name,
        token=p.token,
        language=p.language,
        blacklist_view=False,
        settings_open=False,
    )
    await f.rooms.emit("on_room_created", p, room)
    await f.rooms.send_lobby(bot, chat_id_, p, room)


async def advance_create(f: Flow, bot, chat_id_: int, state: FSMContext, p, index: int) -> None:
    steps = f.cfg.create_steps
    if index >= len(steps):
        await finish_create(f, bot, chat_id_, state, p)
        return
    step = steps[index]
    await state.update_data(step_index=index)
    if getattr(step, "mode", "text") == "choice":
        markup = f.kb.create_choice_step(step, index, lang(f, p))
    else:
        markup = f.kb.cancel(lang(f, p))
    await f.ui.fsm_ask(bot, chat_id_, state, step.prompt(f.texts, lang(f, p)), reply_markup=markup)
    await state.set_state(CreateRoom.extra)


async def fetch_page(f: Flow, page: int, p) -> tuple[list[Room], int]:
    limit = f.cfg.rooms_page_size
    try:
        return await f.backend.list_rooms(
            p, limit=limit, offset=page * limit, statuses=f.cfg.joinable_statuses
        )
    except Exception as exc:
        logger.warning("list_rooms: %s", exc)
        return [], 0


async def open_rooms_list(f: Flow, bot, chat_id_: int, state: FSMContext, p, page: int) -> None:
    limit = f.cfg.rooms_page_size
    items, total = await fetch_page(f, page, p)
    if not items and page == 0 and total == 0:
        await f.ui.fsm_ask(
            bot, chat_id_, state, t(f, p, "JOIN_ROOMS_EMPTY"),
            reply_markup=f.kb.back_only(lang(f, p), f.cb.JoinMethod(method="back").pack()),
        )
        await state.update_data(rooms_page=0)
        await state.set_state(RoomsBrowser.page)
        return
    text = rooms_list_text(items, page, total, limit, f.texts, lang(f, p))
    markup = f.kb.rooms_list(items, page, total, limit, lang(f, p))
    await f.ui.fsm_ask(bot, chat_id_, state, text, reply_markup=markup)
    await state.update_data(rooms_page=page)
    await state.set_state(RoomsBrowser.page)


async def finish_join(f: Flow, bot, chat_id_: int, state: FSMContext, p, result, answer=None) -> None:
    await f.ui.drop_fsm_prompt(bot, chat_id_, state)
    await state.clear()
    if result.error or result.room is None:
        await f.ui.send_notice(bot, chat_id_, err(f, p, result.code or "unknown"))
        await f.rooms.show_menu(bot, chat_id_, p)
        if answer is not None:
            await answer()
        return
    room = result.room
    p.room_code = room.code
    await f.storage.update_binding(
        p.user_id,
        room_code=room.code,
        lobby_message_id=None,
        player_id=p.player_id,
        display_name=p.display_name,
        token=p.token,
        language=p.language,
        blacklist_view=False,
        blacklist_add_message_id=None,
        blacklist_remove_message_id=None,
        settings_open=False,
    )
    await f.rooms.emit("on_room_joined", p, room)
    await f.rooms.send_lobby(bot, chat_id_, p, room)
    await f.rooms.refresh_lobbies(room.code)
    if answer is not None:
        await answer()


async def attempt_join(
    f: Flow,
    bot,
    chat_id_: int,
    state: FSMContext,
    p,
    code: str,
    password: str | None = None,
    *,
    answer=None,
    retry_password: bool = False,
) -> None:
    result = await f.backend.join_room(p, code, password=password)
    if result.error:
        if result.code == ERR_ACCESS_DENIED:
            blacklisted = result.data.get("blacklisted")
            if blacklisted is None:
                try:
                    blacklisted = await f.backend.check_blacklist(p, code)
                except Exception:
                    blacklisted = False
            if blacklisted:
                await f.ui.drop_fsm_prompt(bot, chat_id_, state)
                await state.clear()
                await f.ui.send_notice(bot, chat_id_, t(f, p, "ERR_BLACKLISTED"))
                await f.rooms.show_menu(bot, chat_id_, p)
                if answer is not None:
                    await answer()
                return
            if retry_password:
                prompt = t(f, p, "LOBBY_WRONG_PASSWORD") + "\n\n" + t(f, p, "JOIN_PRIVATE_NEED_PASSWORD")
            else:
                prompt = t(f, p, "JOIN_PRIVATE_NEED_PASSWORD")
            await f.ui.fsm_ask(bot, chat_id_, state, prompt, reply_markup=f.kb.cancel(lang(f, p)))
            await state.update_data(code=code)
            await state.set_state(JoinRoom.password)
            if answer is not None:
                await answer()
            return
        await f.ui.drop_fsm_prompt(bot, chat_id_, state)
        await state.clear()
        await f.ui.send_notice(bot, chat_id_, err(f, p, result.code))
        await f.rooms.show_menu(bot, chat_id_, p)
        if answer is not None:
            await answer()
        return
    await finish_join(f, bot, chat_id_, state, p, result, answer=answer)


async def perform_leave(f: Flow, bot, chat_id_: int, p, room: Room) -> bool:
    result = await f.backend.leave_room(p, room.code)
    if result.error:
        await f.ui.send_notice(bot, chat_id_, err(f, p, result.code))
        return False
    await f.rooms.delete_lobby(bot, chat_id_, p)
    await f.rooms.clear_room(p.user_id)
    await f.ui.send_notice(bot, chat_id_, t(f, p, "LOBBY_LEAVE_NOTIFY"))
    await f.rooms.show_menu(bot, chat_id_, p)
    await f.rooms.emit("on_room_left", p, room)
    if result.data.get("room_deleted"):
        await f.rooms.on_room_deleted(room.code, reason="empty", skip_user_id=p.user_id)
    else:
        await f.rooms.refresh_lobbies(room.code)
        if result.data.get("owner_changed"):
            await f.rooms.emit(
                "on_owner_changed", p, room, new_owner_id=result.data["owner_changed"]
            )
    return True


async def cleanup_blacklist_messages(f: Flow, bot, p) -> None:
    binding = await f.storage.get_binding(p.user_id)
    if binding is None:
        return
    if binding.blacklist_add_message_id:
        await f.ui.try_delete(bot, p.user_id, binding.blacklist_add_message_id)
    if binding.blacklist_remove_message_id:
        await f.ui.try_delete(bot, p.user_id, binding.blacklist_remove_message_id)
    await f.storage.update_binding(
        p.user_id,
        blacklist_view=False,
        blacklist_add_message_id=None,
        blacklist_remove_message_id=None,
    )


async def open_blacklist_view(f: Flow, bot, chat_id_: int, p, room: Room) -> None:
    """Рисует экран ЧС в главном сообщении комнаты (как в исходном боте).

    Важно: редактируется ``lobby_message_id`` из привязки, а не сообщение,
    на котором была нажата кнопка — кнопки «Добавить/Убрать» приходят с
    отдельных временных сообщений.
    """
    binding = await f.storage.get_binding(p.user_id)
    message_id = binding.lobby_message_id if binding else None
    if message_id is None:
        return
    blacklist = await f.backend.get_blacklist(p, room.code)
    names: dict[str, str] = {}
    for entry in blacklist:
        name = await f.storage.get_display_name(entry)
        if name:
            names[entry] = name
    text = format_blacklist_message(
        blacklist, f.texts, lang(f, p), display_name_resolver=lambda e: names.get(e)
    )
    try:
        await bot.edit_message_text(
            chat_id=chat_id_,
            message_id=message_id,
            text=text,
            reply_markup=f.kb.blacklist(lang(f, p)),
            parse_mode=f.cfg.parse_mode,
        )
    except Exception as exc:
        if not f.ui.is_not_modified(exc):
            logger.warning("open_blacklist_view: %s", exc)
    await f.storage.update_binding(p.user_id, blacklist_view=True, settings_open=False)


def register_cancel(f: Flow, router: Router) -> None:
    """Отмена диалогов — регистрируется первой, работает в любой момент."""

    @router.message(F.text.in_(f.cfg.cancel_texts))
    async def cancel_dialog(message: Message, state: FSMContext, **data) -> None:
        try:
            await message.delete()
        except Exception:
            pass
        await f.ui.drop_fsm_prompt(message.bot, message.chat.id, state)
        await state.clear()
        p = await principal(f, message, data)
        binding = await f.storage.get_binding(p.user_id)
        if binding and binding.settings_open and binding.lobby_message_id:
            await f.storage.update_binding(p.user_id, settings_open=False)
            room = await f.rooms.current_room(p)
            if room is not None:
                await f.rooms.render_lobby(
                    message.bot, message.chat.id, binding.lobby_message_id, p, room=room
                )
                return
        await f.rooms.show_menu(message.bot, message.chat.id, p)
