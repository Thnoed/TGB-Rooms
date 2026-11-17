"""Мелкие утилиты, вынесенные из ``app/keyboards/common.py`` и ``app/ui.py``."""

from __future__ import annotations

import base64
import html
import inspect
import secrets
from typing import Any, Awaitable, TypeVar

_T = TypeVar("_T")


def encode_id(value: str) -> str:
    """Кодирует ``player_id`` в base64url.

    ``CallbackData`` не разрешает ``:`` и некоторые другие символы, а
    идентификаторы участников могут их содержать (REST-бэкенды, составные id).
    """
    return base64.urlsafe_b64encode(str(value).encode()).decode().rstrip("=")


def decode_id(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode()).decode()


def escape_html(value: Any) -> str:
    return html.escape(str(value))


def btn_text(text: str, max_len: int = 60) -> str:
    """Обрезает подпись кнопки до лимита Telegram."""
    text = str(text).strip()
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def random_code(length: int = 6) -> str:
    """Ключ комнаты: заглавные буквы и цифры, без неоднозначных символов."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(max(3, length)))


async def maybe_await(value: _T | Awaitable[_T]) -> _T:
    """Позволяет хукам быть как синхронными, так и асинхронными."""
    if inspect.isawaitable(value):
        return await value
    return value  # type: ignore[return-value]
