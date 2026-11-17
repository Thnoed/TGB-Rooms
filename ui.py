"""Хелперы чата: аккуратные сообщения, вопросы FSM, временные уведомления.

Вынесено из ``app/ui.py`` и ``app/handlers/room.py`` (``fsm_ask``,
``drop_fsm_prompt``, ``try_delete``, ``send_notice``). Всё работает через
aiogram ``Bot``; хост может подменить ``UI`` целиком в ``Rooms``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove

logger = logging.getLogger(__name__)


class UI:
    """Набор операций над сообщениями с безопасной обработкой ошибок."""

    def __init__(
        self,
        *,
        notice_lifetime: float = 12.0,
        max_button_len: int = 60,
        parse_mode: str = "HTML",
    ) -> None:
        self.notice_lifetime = notice_lifetime
        self.max_button_len = max_button_len
        self.parse_mode = parse_mode

    async def send(self, bot: Bot, chat_id: int, text: str, **kwargs: Any) -> Message:
        """Отправить сообщение с parse_mode библиотеки по умолчанию."""
        kwargs.setdefault("parse_mode", self.parse_mode)
        return await bot.send_message(chat_id, text, **kwargs)

    async def try_delete(self, bot: Bot, chat_id: int, message_id: int | None) -> None:
        if not message_id:
            return
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception as exc:
            logger.debug("delete_message(%s): %s", message_id, exc)

    async def clear_reply_keyboard(self, bot: Bot, chat_id: int) -> None:
        """Убрать reply-клавиатуру «Отмена» (пустое сообщение + удаление)."""
        try:
            msg = await bot.send_message(chat_id, " ", reply_markup=ReplyKeyboardRemove())
            await bot.delete_message(chat_id, msg.message_id)
        except Exception as exc:
            logger.debug("clear_reply_keyboard: %s", exc)

    def schedule_delete(
        self, bot: Bot, chat_id: int, message_id: int, delay: float | None = None
    ) -> None:
        if not message_id:
            return

        async def _delete_later() -> None:
            await asyncio.sleep(self.notice_lifetime if delay is None else delay)
            await self.try_delete(bot, chat_id, message_id)

        asyncio.create_task(_delete_later())

    async def send_notice(
        self, bot: Bot, chat_id: int, text: str, **kwargs: Any
    ) -> Message | None:
        """Временное уведомление, которое само удалится через ``notice_lifetime``."""
        try:
            msg = await self.send(bot, chat_id, text, **kwargs)
        except Exception as exc:
            logger.warning("send_notice to %s failed: %s", chat_id, exc)
            return None
        self.schedule_delete(bot, chat_id, msg.message_id)
        return msg

    async def fsm_ask(
        self,
        bot: Bot,
        chat_id: int,
        state: FSMContext,
        text: str,
        reply_markup: Any = None,
    ) -> Message:
        """Задать вопрос в диалоге, удалив предыдущий вопрос."""
        data = await state.get_data()
        await self.try_delete(bot, chat_id, data.get("prompt_mid"))
        msg = await self.send(bot, chat_id, text, reply_markup=reply_markup)
        await state.update_data(prompt_mid=msg.message_id)
        return msg

    async def drop_fsm_prompt(self, bot: Bot, chat_id: int, state: FSMContext) -> None:
        data = await state.get_data()
        await self.try_delete(bot, chat_id, data.get("prompt_mid"))
        await state.update_data(prompt_mid=None)

    @staticmethod
    def is_not_modified(exc: Exception) -> bool:
        """Telegram ругается, если текст/клавиатура не изменились — это не ошибка."""
        return isinstance(exc, TelegramBadRequest) and "message is not modified" in str(exc)
