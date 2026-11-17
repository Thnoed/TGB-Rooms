"""Сценарии системы комнат: FSM, колбэки, команды.

Пакет разбит на секции, чтобы ИИ-агент и разработчик читали и правили только
нужную часть, не загружая весь файл (раньше — монолит ``handlers.py``):

- ``_shared`` — общий контекст ``Flow``, хелперы, отмена диалогов;
- ``_create`` — создание комнаты (мастер ``name → privacy → password → …``);
- ``_browser`` — вход по ключу и список активных комнат;
- ``_lobby`` — выход, расформирование, настройки, кастомные кнопки;
- ``_blacklist`` — чёрный список (кик/пардон кнопками и командами).

Публичная точка — ``register_handlers(rooms, router)`` (см. публичный
контракт в ``tgb_rooms.__init__``). Порядок регистрации секций повторяет
порядок исходного монолита: отмена — первой.
"""

from __future__ import annotations

from aiogram import Router

from ._blacklist import register_blacklist
from ._browser import register_browser
from ._create import register_create
from ._lobby import register_lobby
from ._shared import Flow, register_cancel


def register_handlers(rooms, router: Router) -> None:
    """Зарегистрировать все хендлеры системы комнат в переданном ``Router``."""
    f = Flow(
        rooms=rooms,
        cfg=rooms.config,
        cb=rooms.cb,
        ui=rooms.ui,
        kb=rooms.kb,
        texts=rooms.texts,
        backend=rooms.backend,
        storage=rooms.storage,
    )
    register_cancel(f, router)
    register_create(f, router)
    register_browser(f, router)
    register_lobby(f, router)
    register_blacklist(f, router)


__all__ = ["Flow", "register_handlers"]
