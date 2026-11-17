"""FSM-состояния системы комнат (аналог ``app/fsm/states.py``).

Оставлены только сценарии комнаты: создание, вход, просмотр списка.
Кастомные состояния настроек/игры хост заводит в своём роутере — их
состояния не конфликтуют с этими, пока не совпадают имена групп.
"""

from aiogram.fsm.state import State, StatesGroup


class CreateRoom(StatesGroup):
    name = State()
    privacy = State()
    password = State()
    extra = State()  # одно общее состояние для всех кастомных шагов (индекс в FSM-данных)


class JoinRoom(StatesGroup):
    method = State()
    code = State()
    password = State()


class RoomsBrowser(StatesGroup):
    page = State()
    page_input = State()
