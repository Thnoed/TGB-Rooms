"""CallbackData системы комнат.

Классы создаются фабрикой ``build_callbacks(prefix)``: префикс задаётся в
``RoomsConfig.callback_prefix`` (по умолчанию ``tgr``), поэтому колбэки
библиотеки не пересекаются с колбэками бота-хоста. В один Dispatcher можно
включить даже две независимые системы комнат, задав разные префиксы.

Вынесено из ``app/callbacks.py`` ( ``MainMenuCB``, ``PrivacyCB``,
``JoinMethodCB``, ``RoomsListCB``, ``LobbyCB``, ``BlacklistCB``, ``KickCB``,
``PardonCB``, ``LeaveCB`` ).
"""

from __future__ import annotations

from types import SimpleNamespace

from aiogram.filters.callback_data import CallbackData


def build_callbacks(prefix: str = "tgr") -> SimpleNamespace:
    """Собрать namespace классов колбэков с уникальными префиксами."""

    class MenuCB(CallbackData, prefix=f"{prefix}m"):
        action: str  # create | join | list

    class PrivacyCB(CallbackData, prefix=f"{prefix}p"):
        value: str  # yes | no

    class JoinMethodCB(CallbackData, prefix=f"{prefix}j"):
        method: str  # code | list | back

    class RoomsListCB(CallbackData, prefix=f"{prefix}l"):
        action: str  # prev | next | page | pick
        value: str = ""

    class LobbyCB(CallbackData, prefix=f"{prefix}o"):
        action: str  # leave | settings | close_settings | blacklist

    class BlacklistCB(CallbackData, prefix=f"{prefix}b"):
        action: str  # add | remove | back

    class KickCB(CallbackData, prefix=f"{prefix}k"):
        target_id: str  # base64url от player_id

    class PardonCB(CallbackData, prefix=f"{prefix}a"):
        target_id: str  # base64url от player_id

    class CreateStepCB(CallbackData, prefix=f"{prefix}c"):
        index: int  # индекс кастомного шага создания
        value: str

    class LeaveCB(CallbackData, prefix=f"{prefix}v"):
        action: str  # confirm | stay

    class ExtraCB(CallbackData, prefix=f"{prefix}x"):
        index: int  # индекс кнопки из RoomsConfig.extra_lobby_buttons

    return SimpleNamespace(
        Menu=MenuCB,
        Privacy=PrivacyCB,
        JoinMethod=JoinMethodCB,
        List=RoomsListCB,
        Lobby=LobbyCB,
        Blacklist=BlacklistCB,
        Kick=KickCB,
        Pardon=PardonCB,
        CreateStep=CreateStepCB,
        Leave=LeaveCB,
        Extra=ExtraCB,
    )
