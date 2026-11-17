"""Точки расширения: кастомные шаги создания, кнопки лобби и настройки.

Всё, что в ``shelter-tgbot`` было «настройками комнаты» (темы, режимы,
таймеры, карты, боты, старт игры), сюда намеренно не перенесено: библиотека
даёт только каркас, а конкретный проект подключает своё через эти объекты.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

from aiogram import Router
from aiogram.types import CallbackQuery

from .models import Principal, Room, RoomDraft
from .texts import TextProvider


# --- Кастомные шаги мастера создания комнаты ---------------------------------

@dataclass
class StepOutcome:
    """Результат проверки значения шага."""

    ok: bool
    value: Any = None
    error_key: str | None = None
    error_kwargs: dict[str, Any] = field(default_factory=dict)


class CreateStep(Protocol):
    """Шаг после базовых «название → тип → пароль».

    ``mode``: ``"text"`` (ввод сообщением) или ``"choice"`` (inline-кнопки).
    Индекс шага хранится в FSM-данных, поэтому все шаги делят одно состояние
    ``CreateRoom.extra``.
    """

    key: str
    mode: str

    def prompt(self, texts: TextProvider, lang: str) -> str: ...

    def choices(self, texts: TextProvider, lang: str) -> list[tuple[str, str]]: ...

    def validate(
        self, raw: str, principal: Principal, texts: TextProvider, lang: str
    ) -> StepOutcome | Awaitable[StepOutcome]: ...

    def apply(self, draft: RoomDraft, value: Any) -> None: ...


def _apply_value(draft: RoomDraft, apply_field: str, key: str, value: Any) -> None:
    """Пишет значение в поле черновика, в ``settings`` или в ``extra``."""
    if not apply_field:
        draft.extra[key] = value
    elif apply_field in ("name", "is_private", "password", "max_players"):
        setattr(draft, apply_field, value)
    else:
        draft.settings[apply_field] = value


@dataclass
class TextCreateStep:
    """Шаг с вводом текста. ``validator``: ``(raw, principal) -> (ok, value, err)``."""

    key: str
    prompt_key: str
    apply_field: str = ""
    prompt_kwargs: dict[str, Any] = field(default_factory=dict)
    validator: Callable[[str, Principal], Any] | None = None
    mode: str = "text"

    def prompt(self, texts: TextProvider, lang: str) -> str:
        return texts.get(lang, self.prompt_key, **self.prompt_kwargs)

    def choices(self, texts: TextProvider, lang: str) -> list[tuple[str, str]]:
        return []

    def validate(
        self, raw: str, principal: Principal, texts: TextProvider, lang: str
    ) -> StepOutcome:
        if self.validator is None:
            return StepOutcome(True, raw.strip())
        result = self.validator(raw, principal)
        if isinstance(result, StepOutcome):
            return result
        ok, value, error_key = result
        return StepOutcome(bool(ok), value, error_key)

    def apply(self, draft: RoomDraft, value: Any) -> None:
        _apply_value(draft, self.apply_field, self.key, value)


def _choice_label(texts: TextProvider, lang: str, label: str) -> str:
    """Метка кнопки: ключ текста или готовая строка (если ключа нет)."""
    try:
        return texts.get(lang, label)
    except Exception:
        return label


@dataclass
class ChoiceCreateStep:
    """Шаг с выбором из inline-кнопок: ``choices = [(value, label|text_key)]``."""

    key: str
    prompt_key: str
    choices_list: list[tuple[str, str]] = field(default_factory=list)
    apply_field: str = ""
    mode: str = "choice"

    def prompt(self, texts: TextProvider, lang: str) -> str:
        return texts.get(lang, self.prompt_key)

    def choices(self, texts: TextProvider, lang: str) -> list[tuple[str, str]]:
        return [(value, _choice_label(texts, lang, label)) for value, label in self.choices_list]

    def validate(
        self, raw: str, principal: Principal, texts: TextProvider, lang: str
    ) -> StepOutcome:
        return StepOutcome(True, raw)

    def apply(self, draft: RoomDraft, value: Any) -> None:
        _apply_value(draft, self.apply_field, self.key, value)


class MaxPlayersStep(TextCreateStep):
    """Готовый пример кастомного шага: максимум участников.

    В исходном боте этот шаг был частью мастера создания и брал границы из
    ``GET /settings-limits`` ядра. Здесь он вынесен в расширение: подключите
    ``RoomsConfig(create_steps=[MaxPlayersStep(lo=2, hi=12)])``, чтобы
    вернуть поведение «как было», или замените своим шагом.
    """

    def __init__(self, lo: int = 2, hi: int = 100, apply_field: str = "max_players") -> None:
        self.lo = lo
        self.hi = hi
        super().__init__(
            key="max_players",
            prompt_key="CREATE_MAX_PLAYERS_PROMPT",
            apply_field=apply_field,
            prompt_kwargs={"lo": lo, "hi": hi},
        )

    def validate(
        self, raw: str, principal: Principal, texts: TextProvider, lang: str
    ) -> StepOutcome:
        try:
            value = int(str(raw).strip())
        except ValueError:
            return StepOutcome(False, error_key="CREATE_NUMBER_NAN", error_kwargs={"lo": self.lo, "hi": self.hi})
        if not (self.lo <= value <= self.hi):
            return StepOutcome(False, error_key="CREATE_NUMBER_RANGE", error_kwargs={"lo": self.lo, "hi": self.hi})
        return StepOutcome(True, value)


# --- Дополнительные кнопки главного сообщения комнаты ------------------------

@dataclass
class LobbyButton:
    """Кнопка в главном сообщении комнаты (старт игры, боты, чат, ...).

    ``handler``: ``async (callback, room, principal, rooms) -> None``.
    Библиотека сама регистрирует колбэк с уникальным префиксом; если
    ``handler`` не задан, на нажатие отвечает «заглушка».
    """

    text: str | Callable[..., str]
    visible: Callable[[Room, Principal], bool] | None = None
    handler: Callable[..., Any] | None = None

    def label(self, room: Room, principal: Principal, texts: TextProvider, lang: str) -> str:
        if callable(self.text):
            return str(self.text(room, principal, texts, lang))
        return str(self.text)

    def is_visible(self, room: Room, principal: Principal) -> bool:
        return self.visible(room, principal) if self.visible is not None else True


# --- Кастомные настройки комнаты ---------------------------------------------

@dataclass
class SettingsContext:
    """Всё, что нужно расширению настроек для отрисовки своего экрана."""

    rooms: Any  # Rooms (объявлено строкой, чтобы не было циклического импорта)
    callback: CallbackQuery
    room: Room
    principal: Principal
    lang: str

    @property
    def bot(self):
        return self.callback.bot or self.rooms.bot

    @property
    def chat_id(self) -> int:
        return self.callback.message.chat.id

    @property
    def message_id(self) -> int:
        return self.callback.message.message_id

    def close_callback(self) -> str:
        """Готовый ``callback_data`` для кнопки «Назад в лобби»."""
        return self.rooms.settings_close_callback()

    async def close(self) -> None:
        """Вернуть главное сообщение комнаты (вызывает библиотека по кнопке)."""
        await self.rooms.storage.update_binding(self.principal.user_id, settings_open=False)
        await self.rooms.render_lobby(
            self.bot, self.chat_id, self.message_id, self.principal, room=self.room
        )


class SettingsExtension(Protocol):
    """Расширение «Настройки комнаты», полностью определяемое хостом.

    Библиотека только добавляет кнопку в лобби и вызывает ``open(ctx)``;
    содержимое экрана, клавиатура, свои FSM-состояния и колбэки — на стороне
    проекта. ``build_router`` (необязательный) включается внутрь роутера
    системы комнат, поэтому его обработчики получают тот же DI-контекст.
    """

    def button_text(
        self, room: Room, principal: Principal, texts: TextProvider, lang: str
    ) -> str | None: ...

    def is_available(self, room: Room, principal: Principal) -> bool: ...

    async def open(self, ctx: SettingsContext) -> None: ...

    def build_router(self, rooms: Any) -> Router | None: ...
