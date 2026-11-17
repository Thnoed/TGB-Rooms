# tgb-rooms — абстрактная система комнат для Telegram-ботов

Переиспользуемая библиотека на **aiogram 3**: создание комнат, вход по ключу,
список активных комнат, чёрный список и главное сообщение комнаты с кнопками.

Проект получен выносом «комнатной» части из `shelter-tgbot`: из его
`app/handlers/room.py`, `app/fsm/states.py`, `app/callbacks.py`,
`app/keyboards/rooms.py`, `app/keyboards/lobby.py`, `app/messages/lobby.py`,
`app/locales/*.yaml`, `app/ui.py`, `app/storage.py` и `app/api_client.py`
взяты сценарии и структуры, а всё, что привязывало их к игре «Укрытие»
(темы, режимы, таймеры, карты, боты, готовность, WS, БД, главное меню),
заменено на контракты и точки расширения.

Исходный бот **не изменён**. `tgb-rooms` — самостоятельный пакет: скопируйте
папку `tgb_rooms/` в свой проект (или добавьте родительскую папку в
`PYTHONPATH`) и подключите роутер.

---

## Что работает «из коробки»

| Возможность | Описание |
|---|---|
| Создание комнаты | Мастер `название → тип (приватная/открытая) → пароль`. Пароль спрашивается только для приватной. Ключ комнаты генерируется бэкендом. |
| Вход по ключу | `/join <CODE>`, диалог «по коду / из списка», запрос пароля для приватной комнаты, проверка чёрного списка. |
| Список активных комнат | Открытые комнаты, к которым можно подключиться; постраничный просмотр (`prev/next`), переход на страницу по номеру, кнопка выбора комнаты, «Назад». |
| Чёрный список | Встроенный экран ЧС в главном сообщении: просмотр, исключение участника (`+` в ЧС), удаление из ЧС, команды `/kick <ник>` и `/pardon <ник>`, ограничение «владелец + статус waiting». |
| Главное сообщение комнаты | Название, ключ, тип, статус, список участников с отметками 👑/🤖/🚪, блок настроек и кнопки (выход, ЧС, кастомные, настройки). Автообновление у всех участников. |
| Выход и удаление | `/leave`, кнопка «Выйти», подтверждение выхода (по хуку), `/disband` + `/confirm <CODE>` для владельца. |
| Два бэкенда | `MemoryRoomsBackend` (автономно, без сервера) и `RestRoomsBackend` (адаптер под REST в стиле `shelter-core`). |
| События и хуки | `Hooks`, `notify_room_changed`, `refresh_lobbies`, `on_room_deleted` для интеграции с WebSocket/игрой/админкой. |

## Чего здесь нет (и это сделано намеренно)

Система комнат ничего не знает о вашем продукте. Всё ниже кастомизируется под
конкретный бота через `RoomsConfig` и точки расширения:

- настройки комнаты (темы, режимы, таймеры, карты, любые поля);
- игровая логика, старт/готовность, боты, чат комнаты;
- главное меню бота, регистрация пользователя, профиль, язык;
- способ хранения (БД, Redis, внешний сервер);
- движок i18n и набор языков;
- WebSocket и рассылка событий;
- внешний вид сообщений и набор кнопок.

---

## Быстрый старт

```python
import asyncio
import os

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from tgb_rooms import Rooms, RoomsConfig, MemoryRoomsBackend, MaxPlayersStep


async def main() -> None:
    bot = Bot(
        token=os.environ["TG_BOT_TOKEN"],
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())  # FSM-хранилище обязательно

    rooms = Rooms(
        backend=MemoryRoomsBackend(),
        config=RoomsConfig(
            default_language="ru",
            # пример кастомного шага: вернуть «максимум игроков» как в исходном боте
            create_steps=[MaxPlayersStep(lo=2, hi=12)],
        ),
    )
    rooms.attach_bot(bot)

    host_router = Router()

    @host_router.message(CommandStart())
    async def start(message: Message) -> None:
        # Встраиваем кнопки системы комнат в своё меню:
        await message.answer(
            "<b>Главное меню</b>",
            reply_markup=rooms.entry_keyboard("ru"),
        )

    dp.include_router(host_router)
    dp.include_router(rooms.build_router())  # до catch-all/fallback-хендлеров

    await dp.start_polling(bot)


asyncio.run(main())
```

Минимальные зависимости: `aiogram>=3.13`. `aiohttp` нужен только при
использовании `RestRoomsBackend` (импортируется лениво).

---

## Архитектура

```
Telegram → aiogram Dispatcher → rooms.build_router() → handlers/
                                      │
                                      ├─ Rooms (core.py) — фасад/оркестратор
                                      │    ├─ RoomsBackend  (backend.py) — где живут комнаты
                                      │    ├─ RoomsStorage (storage.py) — привязки пользователей
                                      │    ├─ TextProvider (texts.py)   — строки ru/en
                                      │    ├─ Keyboards    (keyboards.py)
                                      │    ├─ UI           (ui.py)
                                      │    └─ extensions / hooks / config
                                      └─ FSM (states.py) + callbacks.py
```

## Публичный контракт

Встраивание — **только через импорты** из `tgb_rooms` (см. `__all__` в
`tgb_rooms/__init__.py`): имена, сигнатуры и поведение стабильны между
минорными версиями, новые поля `RoomsConfig` всегда опциональны, значения по
умолчанию означают «как в исходном боте». Внутреннее устройство
(`handlers/_*.py` и детали `core`) для стандартных задач трогать не нужно —
но файлы нарочно маленькие: для сложной логики откройте только нужную секцию
(`_create.py`, `_browser.py`, `_lobby.py`, `_blacklist.py`, общий `_shared.py`),
а после правок запустите `python -m pytest tests/ -q` из корня `tgb-rooms`
(регрессия фиксирует уже отлаженное поведение).

| Файл | Роль | Откуда пришло |
|---|---|---|
| `core.py` | `Rooms`: резолвинг пользователя, рендер лобби, `refresh_lobbies`, хуки, внешние события, сборка роутера | `send_lobby_message`, `refresh_room_lobbies`, `clear_room`, `_on_room_deleted` |
| `handlers/__init__.py` | `register_handlers(rooms, router)` — вход в сценарии | `app/handlers/room.py` |
| `handlers/_shared.py` | `Flow`, отмена диалогов, общие хелперы (вход/выход/ЧС) | `app/handlers/room.py` (хелперы) |
| `handlers/_create.py` | мастер создания (имя → тип → пароль → кастомные шаги) | `app/handlers/room.py` (создание) |
| `handlers/_browser.py` | вход по ключу, список комнат, пагинация | `app/handlers/room.py` (вход/список) |
| `handlers/_lobby.py` | выход, `/disband`, настройки, кастомные кнопки | `app/handlers/room.py` (лобби/настройки) |
| `handlers/_blacklist.py` | экран ЧС, кик/пардон (кнопки и `/kick`/`/pardon`) | `app/handlers/room.py` (ЧС) |
| `models.py` | `Room`, `Member`, `RoomDraft`, `RoomResult`, `Principal`, `Identity`, `UserBinding` | `state` из API + `UserData` |
| `backend.py` | ABC-контракт `RoomsBackend`, коды ошибок | `app/api_client.py` (контракт) |
| `memory_backend.py` | in-memory реализация (по умолчанию) | новая, автономная |
| `rest_backend.py` | REST-адаптер + `RestEndpoints` | `app/api_client.py` |
| `storage.py` | `RoomsStorage`, `InMemoryRoomsStorage` | `app/storage.py` |
| `states.py` | `CreateRoom`, `JoinRoom`, `RoomsBrowser` | `app/fsm/states.py` |
| `callbacks.py` | `build_callbacks(prefix)` | `app/callbacks.py` |
| `keyboards.py` | все inline/reply-клавиатуры | `app/keyboards/rooms.py`, `lobby.py`, `menus.py` |
| `messages.py` | `format_lobby_message`, `format_blacklist_message`, `rooms_list_text` | `app/messages/lobby.py`, `_rooms_list_text` |
| `texts.py` | RU/EN строки, `TextProvider`, `DefaultTexts` | `app/locales/ru.yaml`, `en.yaml` |
| `ui.py` | `try_delete`, `send_notice`, `fsm_ask`, `clear_reply_keyboard` | `app/ui.py` |
| `extensions.py` | `CreateStep`, `MaxPlayersStep`, `LobbyButton`, `SettingsExtension`, `SettingsContext` | вместо «настроек комнаты» |
| `config.py` | `RoomsConfig`, `Hooks`, команды по умолчанию | `app/config.py` (лимиты) |
| `utils.py` | `encode_id`/`decode_id`, `escape_html`, `btn_text`, `random_code` | `app/keyboards/common.py` |

**Что не перенесено, а заменено точкой расширения:** темы/режимы/таймеры/карты
и весь экран настроек → `SettingsExtension`; кнопки «Начать игру», «Боты» →
`LobbyButton`; `max_players` в мастере → `MaxPlayersStep`; WS-события →
`Hooks` + `notify_room_changed`; главное меню → `on_show_menu` /
`entry_keyboard`; БД → `RoomsStorage`; регистрация сессии → `identity_resolver`.

---

## Контракт бэкенда (`RoomsBackend`)

Бэкенд — единственное место, где «живут» комнаты. Все методы асинхронные,
принимают `Principal` и возвращают `RoomResult` / `Room` / список.

```python
class RoomsBackend(ABC):
    async def create_room(principal, draft: RoomDraft) -> RoomResult: ...
    async def join_room(principal, code, password=None) -> RoomResult: ...
    async def leave_room(principal, code) -> RoomResult: ...
    async def disband_room(principal, code) -> RoomResult: ...
    async def get_room(principal, code) -> Room | None: ...
    async def list_rooms(principal, limit, offset, statuses=None) -> tuple[list[Room], int]: ...
    async def get_blacklist(principal, code) -> list[str]: ...
    async def check_blacklist(principal, code) -> bool: ...
    async def kick(principal, code, target_player_id) -> RoomResult: ...
    async def pardon(principal, code, target_player_id) -> RoomResult: ...
    # необязательные (по умолчанию not_supported):
    async def update_settings(principal, code, settings) -> RoomResult: ...
    async def set_password(principal, code, password) -> RoomResult: ...
```

`RoomResult.ok` / `.error`, `.room` (снимок при успехе), `.code`, `.message`,
`.data` (доп. поля, например `blacklisted`, `password_required`,
`owner_changed`, `room_deleted`).

Стандартные коды ошибок (мапятся на тексты через `ERROR_TEXT_KEYS` в
`texts.py`): `room_not_found`, `room_full`, `invalid_room_state`,
`already_in_room`, `room_access_denied`, `forbidden`, `player_not_found`,
`self_kick`, `not_supported`, `connection_error`.

Для `join_room` при `room_access_denied` положите в `data` флаг
`blacklisted=True` (бот покажет «вы в ЧС») или `password_required=True`
(бот спросит пароль); если флагов нет, бот сам вызовет `check_blacklist`.

### Готовые бэкенды

- **`MemoryRoomsBackend`** — комнаты в памяти процесса. Умеет всё: генерацию
  ключа, пароли, лимит участников, передачу владения при выходе владельца,
  ЧС, `update_settings`, `set_password`, `set_status`. Состояние теряется при
  рестарте — для персистентности напишите свой бэкенд/хранилище.
- **`RestRoomsBackend`** — адаптер под REST API. Пути настраиваются
  `RestEndpoints`, разбор ответа — `room_parser`, заголовки —
  `headers_factory`; токен берётся из `Principal.token`.

```python
from tgb_rooms import RestRoomsBackend, RestEndpoints

backend = RestRoomsBackend(
    "http://localhost:8000/api/v1",
    endpoints=RestEndpoints(create="/rooms", list="/rooms?limit={limit}&offset={offset}"),
    timeout=10.0,
)
```

---

## Хранилище привязок (`RoomsStorage`)

Библиотека помнит, в какой комнате пользователь, id главного сообщения,
открыт ли экран ЧС/настроек, язык и кэш имён. `InMemoryRoomsStorage` — по
умолчанию. Чтобы пережить рестарт, реализуйте адаптер поверх своей БД:

```python
class MyStorage(RoomsStorage):
    async def get_binding(self, user_id): ...
    async def set_binding(self, binding): ...
    async def update_binding(self, user_id, **kwargs): ...
    async def clear_room(self, user_id): ...
    async def get_users_in_room(self, code): ...
    async def get_display_name(self, player_id): ...
    async def set_display_name(self, player_id, name): ...
    async def get_language(self, user_id): ...
    async def set_language(self, user_id, lang): ...
```

`UserBinding` — аналог «комнатной» части `UserData`: `user_id`, `player_id`,
`display_name`, `token`, `language`, `room_code`, `lobby_message_id`,
`menu_message_id`, `blacklist_view`, `blacklist_add_message_id`,
`blacklist_remove_message_id`, `settings_open`, `extra`.

---

## Идентичность и язык

По умолчанию `player_id = str(telegram_id)`, имя — `full_name`, язык —
`config.default_language`, токена нет. Если у бота уже есть своя модель
пользователя и/или серверный токен, задайте `identity_resolver`:

```python
from tgb_rooms import Identity

def resolve_identity(event, data):
    user = data["event_from_user"]           # aiogram User
    mine = my_db.get(user.id)                # ваша модель
    return Identity(
        user_id=user.id,
        player_id=mine.player_id,            # ключ в бэкенде комнат
        display_name=mine.nick or user.full_name,
        token=mine.api_token,                # для RestRoomsBackend
        language=mine.language,
        extra={"any": "payload"},
    )

config = RoomsConfig(
    identity_resolver=resolve_identity,
    language_resolver=lambda user_id, data: my_db.get(user_id).language,
)
```

`Rooms.resolve_principal()` собирает `Principal` = `Identity` + текущая
привязка к комнате. Все хуки, рендереры и расширения получают `Principal`.

---

## Тексты и локализация

`TextProvider` — любой объект с `get(lang, key, **kwargs)`, `table(lang, key)`,
`status_title(lang, status)`. Встроенный `DefaultTexts` содержит ru/en строки
(перенесены из `ru.yaml`/`en.yaml`) и таблицу `STATUS_TITLES`.

Три способа подменить строки:

1. `RoomsConfig.text_overrides = {"ru": {"CREATE_NAME_PROMPT": "Как назовём?"}}`;
2. `RoomsConfig.texts = default_texts` — свой объект-провайдер (обёртка над
   вашими yaml/gettext/БД);
3. `RoomsConfig.texts = lambda lang, key, **kw: my_i18n(lang, key, **kw)`.

Все сообщения библиотеки — **HTML**. `RoomsConfig.parse_mode` по умолчанию
`"HTML"` и передаётся явно при отправке, перекрывая настройки `Bot`. Если бот
работает в Markdown, задайте свой `parse_mode` и совместимые тексты.

Плейсхолдеры `{name}`, `{code}`, `{lo}`, `{hi}`, `{cur}`, `{total}`, `{field}`,
`{value}` подставляются через `str.format`. Ключи верхнего регистра можно
посмотреть в `tgb_rooms/texts.py` (`_RU`, `_EN`, `ERROR_TEXT_KEYS`,
`EVENT_TEXT_KEYS`).

---

## Точки расширения

### Дополнительные шаги создания (`CreateStep`)

Базовый мастер: `name → privacy → password`. Дальше идут шаги из
`create_steps` (все делят состояние `CreateRoom.extra`, индекс шага лежит в
FSM-данных).

```python
from tgb_rooms import TextCreateStep, ChoiceCreateStep, MaxPlayersStep, StepOutcome

# текстовый шаг с валидацией (пишет в draft.settings["difficulty"])
difficulty = TextCreateStep(
    key="difficulty",
    prompt_key="CREATE_NAME_PROMPT",        # или свой ключ в text_overrides
    apply_field="difficulty",
    validator=lambda raw, p: (raw.lower() in {"easy", "hard"}, raw.lower(), "CREATE_NAME_ERROR"),
)

# шаг-выбор (inline-кнопки)
mode = ChoiceCreateStep(
    key="mode",
    prompt_key="CREATE_PRIVACY_PROMPT",
    choices_list=[("classic", "Classic"), ("fast", "Fast")],
    apply_field="mode",
)

config = RoomsConfig(create_steps=[MaxPlayersStep(lo=2, hi=12), mode])
```

`step.apply(draft, value)` пишет в `RoomDraft`: `apply_field` из
`name/is_private/password/max_players`, иначе в `draft.settings[...]`; если
`apply_field` пуст — в `draft.extra[key]`.

### Кнопки в главном сообщении (`LobbyButton`)

```python
from tgb_rooms import LobbyButton

async def on_start(callback, room, principal, rooms):
    await my_game.start(room.code)
    await callback.answer("Игра началась!")

config = RoomsConfig(extra_lobby_buttons=[
    LobbyButton(
        text="▶️ Начать игру",
        visible=lambda room, p: room.is_owner(p.player_id) and room.status == "waiting",
        handler=on_start,
    ),
])
```

Библиотека сама генерирует колбэк (`ExtraCB(index=i)`) и регистрирует
обработчик. Индекс стабилен для всех кнопок списка.

### Настройки комнаты (`SettingsExtension`)

Настроек «по умолчанию» нет — это полностью ваш код. Расширение добавляет
кнопку в лобби и отрисовывает свой экран (обычно редактированием того же
главного сообщения, как в исходном боте).

```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tgb_rooms import SettingsContext

class MySettings:
    def button_text(self, room, principal, texts, lang):
        return texts.get(lang, "SETTINGS") if room.is_owner(principal.player_id) else None

    def is_available(self, room, principal):
        return room.is_owner(principal.player_id) and room.status in {"waiting"}

    async def open(self, ctx: SettingsContext) -> None:
        # ctx.bot, ctx.chat_id, ctx.message_id, ctx.room, ctx.principal, ctx.lang, ctx.rooms
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Назад", callback_data=ctx.close_callback()),
            InlineKeyboardButton(text="Сменить пароль", callback_data="myset:pwd"),
        ]])
        await ctx.rooms.ui.send(ctx.bot, ctx.chat_id, "⚙️ Мои настройки", reply_markup=kb)

    def build_router(self, rooms):
        # свой Router со своими FSM-состояниями и колбэками; включается внутрь роутера библиотеки
        return my_settings_router

config = RoomsConfig(settings_extension=MySettings())
```

`ctx.close()` и `ctx.close_callback()` возвращают пользователя в лобби. Пока
открыты настройки, `refresh_lobbies` не перерисовывает сообщение
(`settings_open=True`).

### Прочие кастомизации

| Поле `RoomsConfig` | Что меняет |
|---|---|
| `room_info_renderer(room, principal, rooms, lang) -> str` | полный текст главного сообщения |
| `settings_summary(room, principal, rooms) -> list[str]` | строки блока «Настройки» |
| `can_manage(room, principal) -> bool` | право на ЧС/настройки (по умолчанию владелец + `editable_statuses`) |
| `needs_leave_confirm(room, principal) -> bool` | нужен ли экран подтверждения выхода |
| `on_show_menu(bot, chat_id, principal, rooms)` | ваше главное меню после отмены/выхода/удаления комнаты |
| `extra_routers: list[Router]` | свои роутеры внутри роутера библиотеки |
| `joinable_statuses` / `editable_statuses` | какие статусы считать «можно войти» / «можно управлять» |

---

## Хуки и внешние события

```python
from tgb_rooms import Hooks

async def on_created(*, rooms, principal, room, **payload):
    await analytics.track("room_created", room.code)

config = RoomsConfig(hooks=Hooks(
    on_room_created=on_created,
    on_room_joined=..., on_room_left=..., on_room_disbanded=...,
    on_room_deleted=..., on_room_changed=...,
    on_member_joined=..., on_member_left=..., on_member_kicked=...,
    on_member_pardoned=..., on_owner_changed=...,
    on_blacklist_changed=..., on_settings_changed=..., on_error=...,
))
```

Сигнатура любого хука: `async def hook(*, rooms, principal, room, **payload)`.
Для внешних событий `principal` может быть `None`, `room` — снимком или `None`.
Исключения хуков логируются и не роняют сценарий (вызывается `on_error`).

Для WebSocket/игры/админки есть три публичные точки (`core.py`):

```python
await rooms.refresh_lobbies(code)                    # перерисовать лобби у всех участников
await rooms.notify_room_changed(code, "player_joined", name="Anna")  # хуки + уведомления + refresh
await rooms.on_room_deleted(code, reason="ws")       # снять привязки, уведомить, показать меню
```

`notify_room_changed` принимает `refresh=`, `notify=`, любые `**payload`
(попадают в хук и в текст уведомления). Текст уведомления берётся из
`RoomsConfig.event_text_keys`, рассылка включается `notify_events=True`
или `notify=True`. Имена событий → хуки: `player_joined`, `player_left`,
`player_kicked`, `owner_changed`, `room_deleted`, `blacklist_changed`,
`settings_updated` (плюс общий `on_room_changed`).

---

## Команды и колбэки

Команды задаются `RoomsConfig.commands` (по умолчанию):

| Действие | Команды |
|---|---|
| Создать | `/create`, `/createroom`, `/newroom` |
| Войти | `/join`, `/joinroom` (можно сразу `/join <CODE>`) |
| Список комнат | `/rooms`, `/roomlist` |
| Выйти | `/leave` |
| Удалить комнату | `/disband` → `/confirm <CODE>` |
| Чёрный список | `/kick <ник>`, `/pardon <ник>` |
| Отмена диалога | `/cancel`, `Отмена`, `Cancel`, `❌ Отмена` (`cancel_texts`) |

Все `CallbackData` создаются `build_callbacks(config.callback_prefix)`;
префикс по умолчанию `tgr`: `tgrm` (меню), `tgrp` (приватность), `tgrj`
(способ входа), `tgrl` (список), `tglo` (лобби), `tgrb` (ЧС), `tgrk`
(кик), `tgra` (пардон), `tgrc` (шаг создания), `tgrv` (подтверждение выхода),
`tgrx` (кастомные кнопки). Задайте свой `callback_prefix`, если бот уже
использует такие строки.

FSM: `CreateRoom(name → privacy → password → extra)`,
`JoinRoom(method → code → password)`, `RoomsBrowser(page ↔ page_input)`.
В диалогах предыдущий вопрос удаляется (`UI.fsm_ask`), reply-клавиатура
«Отмена» снимается при возврате в меню.

---

## Справочник `RoomsConfig`

| Группа | Поля (значение по умолчанию) |
|---|---|
| Язык/тексты | `default_language="ru"`, `texts=None`, `text_overrides={}` |
| Лимиты | `rooms_page_size=10`, `name_min_len=1`, `name_max_len=60`, `password_min_len=1`, `password_max_len=64`, `default_max_players=8`, `max_players_min=2`, `max_players_max=100`, `code_length=6`, `code_factory=None` |
| UI | `notice_lifetime=12.0`, `max_button_len=60`, `parse_mode="HTML"`, `delete_menu_on_action=True` |
| Команды | `commands=DEFAULT_COMMANDS`, `cancel_texts=...`, `callback_prefix="tgr"` |
| Интеграция | `identity_resolver=None`, `language_resolver=None`, `bot=None` |
| Статусы | `joinable_statuses={"waiting"}`, `editable_statuses={"waiting"}`, `can_manage=None`, `needs_leave_confirm=None` |
| Рендер | `room_info_renderer=None`, `settings_summary=None` |
| Расширения | `create_steps=[]`, `settings_extension=None`, `extra_lobby_buttons=[]`, `extra_routers=[]`, `on_show_menu=None` |
| События | `hooks=Hooks()`, `notify_events=False`, `event_text_keys={...}` |

---

## Ограничения

- `MemoryRoomsBackend` и `InMemoryRoomsStorage` хранят состояние в одном
  процессе; для кластера/рестарта реализуйте свои `RoomsBackend`/`RoomsStorage`.
- Библиотека не регистрирует пользователей и не знает токенов — это
  `identity_resolver` и `Principal.token`.
- Сообщения по умолчанию используют HTML-разметку.
- Роутер нужно включать **до** catch-all/fallback-хендлеров бота; для FSM
  необходим `Dispatcher(storage=...)`.
- Отмена (`cancel_texts`) перехватывается глобально внутри роутера; если у
  расширения своя логика отмены, настройте `cancel_texts` или подключите свой
  роутер раньше.

---

## Файлы проекта

```
tgb-rooms/
├── AGENTS.md          # инструкция для ИИ-агента по встраиванию (English)
├── README.md          # этот файл
├── tests/             # регрессия поведения (pytest): создание/вход/ЧС,
│                      # расширения/события/REST-парсинг, список/пароль/отмена
└── tgb_rooms/
    ├── __init__.py    # публичный API (стабильный контракт, см. раздел выше)
    ├── core.py        # Rooms: фасад, рендер, события, build_router()
    ├── handlers/
    │   ├── __init__.py    # register_handlers() — вход в сценарии
    │   ├── _shared.py     # Flow, отмена диалогов, общие хелперы
    │   ├── _create.py     # мастер создания
    │   ├── _browser.py    # вход по ключу, список комнат
    │   ├── _lobby.py      # выход, disband, настройки, кастомные кнопки
    │   └── _blacklist.py  # чёрный список
    ├── models.py      # Room / Member / RoomDraft / RoomResult / Principal / UserBinding
    ├── backend.py     # контракт RoomsBackend + коды ошибок
    ├── memory_backend.py
    ├── rest_backend.py
    ├── storage.py     # RoomsStorage / InMemoryRoomsStorage
    ├── states.py      # FSM-состояния
    ├── callbacks.py   # build_callbacks()
    ├── keyboards.py   # Keyboards
    ├── messages.py    # форматирование сообщений
    ├── texts.py       # RU/EN строки, TextProvider
    ├── ui.py          # UI-хелперы
    ├── extensions.py  # CreateStep / LobbyButton / SettingsExtension
    ├── config.py      # RoomsConfig / Hooks
    └── utils.py       # encode_id, escape_html, btn_text, random_code
```
