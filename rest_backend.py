"""REST-адаптер: подключение системы комнат к внешнему API.

Вынесено из ``app/api_client.py`` (методы, отвечающие за комнаты) и
``app/limits.py``. Формы запросов/ответов по умолчанию повторяют
``shelter-core``: ``{"error": true, "code": ..., "message": ...}``,
``GET /rooms?limit&offset`` → ``{"items": [...], "total": ...}``,
``GET /rooms/{code}/state`` → снимок комнаты.

Адаптер не привязан к конкретному серверу: пути настраиваются через
``RestEndpoints``, а разбор ответа — через ``room_parser``. ``aiohttp``
импортируется лениво, поэтому сам пакет ``tgb_rooms`` работает и без него.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable

from .backend import ERR_CONNECTION, RoomsBackend
from .models import ACTIVE, Member, Principal, Room, RoomDraft, RoomResult

logger = logging.getLogger(__name__)


@dataclass
class RestEndpoints:
    """Шаблоны путей. Поддерживают ``{code}``, ``{limit}``, ``{offset}``."""

    create: str = "/rooms"
    join: str = "/rooms/{code}/join"
    leave: str = "/rooms/{code}/leave"
    disband: str = "/rooms/{code}/disband"
    state: str = "/rooms/{code}/state"
    list: str = "/rooms?limit={limit}&offset={offset}"
    blacklist: str = "/rooms/{code}/blacklist"
    check_blacklist: str = "/rooms/{code}/check_blacklist"
    kick: str = "/rooms/{code}/kick"
    pardon: str = "/rooms/{code}/pardon"
    settings: str = "/rooms/{code}/settings"
    password: str = "/rooms/{code}/password"


class RestRoomsBackend(RoomsBackend):
    """Бэкенд поверх REST API.

    :param base_url: базовый URL, например ``http://localhost:8000/api/v1``.
    :param endpoints: шаблоны путей под ваш сервер.
    :param room_parser: ``(dict) -> Room``, если формат ответа отличается.
    :param headers_factory: ``(principal) -> dict`` для дополнительных заголовков.
    """

    def __init__(
        self,
        base_url: str,
        *,
        endpoints: RestEndpoints | None = None,
        timeout: float = 10.0,
        retries: int = 2,
        retry_delay: float = 1.0,
        session: Any = None,
        room_parser: Callable[[dict], Room] | None = None,
        headers_factory: Callable[[Principal], dict] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.endpoints = endpoints or RestEndpoints()
        self.timeout = timeout
        self.retries = max(1, retries)
        self.retry_delay = retry_delay
        self._session = session
        self.room_parser = room_parser
        self.headers_factory = headers_factory

    async def get_session(self) -> Any:
        if self._session is None or self._session.closed:
            import aiohttp

            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def _headers(self, principal: Principal | None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if principal is not None and principal.token:
            headers["Authorization"] = f"Bearer {principal.token}"
        if self.headers_factory is not None and principal is not None:
            headers.update(self.headers_factory(principal))
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        principal: Principal | None = None,
        json: dict | None = None,
    ) -> dict[str, Any]:
        import aiohttp

        url = f"{self.base_url}{path}"
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            session = await self.get_session()
            try:
                async with session.request(
                    method,
                    url,
                    headers=self._headers(principal),
                    json=json,
                    timeout=timeout,
                ) as resp:
                    if resp.status == 204:
                        return {"data": None}
                    data = await resp.json(content_type=None)
                    if resp.status >= 400:
                        error = data.get("error", {}) if isinstance(data, dict) else {}
                        if not isinstance(error, dict):
                            error = {}
                        return {
                            "error": True,
                            "code": str(error.get("code") or f"http_{resp.status}"),
                            "message": str(error.get("message") or resp.reason or "Unknown error"),
                        }
                    return data if isinstance(data, dict) else {"data": data}
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # aiohttp.ClientError, asyncio.TimeoutError, ...
                last_error = exc
                await self.close()
                logger.error(
                    "API %s %s (попытка %d/%d): %s",
                    method, url, attempt, self.retries, exc,
                )
                if attempt < self.retries:
                    await asyncio.sleep(self.retry_delay)
        return {"error": True, "code": ERR_CONNECTION, "message": str(last_error)}

    # --- разбор ответов ------------------------------------------------------

    def _parse_room(self, data: dict) -> Room | None:
        if not isinstance(data, dict):
            return None
        if self.room_parser is not None:
            return self.room_parser(data)
        players: list[Member] = []
        for player in data.get("players") or []:
            if not isinstance(player, dict):
                continue
            players.append(
                Member(
                    player_id=str(
                        player.get("player_id")
                        or player.get("external_id")
                        or player.get("id")
                        or ""
                    ),
                    display_name=str(player.get("display_name") or player.get("name") or ""),
                    is_bot=bool(player.get("is_bot")),
                    state=str(player.get("state") or ACTIVE),
                    extra=dict(player.get("extra") or {}),
                )
            )
        settings = dict(data.get("settings") or {})
        try:
            max_players = int(data.get("max_players") or settings.get("max_players") or 0)
        except (TypeError, ValueError):
            max_players = 0
        extra = dict(data.get("extra") or {})
        if data.get("owner_display"):
            extra["owner_display"] = data["owner_display"]
        if data.get("players_count") is not None:
            extra["players_count"] = data["players_count"]
        return Room(
            code=str(data.get("code") or ""),
            name=str(data.get("name") or ""),
            owner_id=str(data.get("owner_id") or ""),
            is_private=bool(data.get("is_private")),
            has_password=bool(data.get("is_private") or data.get("has_password")),
            max_players=max_players or 8,
            status=str(data.get("status") or "waiting"),
            members=players,
            blacklist=[str(x) for x in (data.get("blacklist") or [])],
            settings=settings,
            extra=extra,
        )

    @staticmethod
    def _result(res: dict, room: Room | None = None) -> RoomResult:
        if not isinstance(res, dict):
            return RoomResult.success(room)
        if res.get("error"):
            extra = {
                k: v for k, v in res.items() if k not in ("error", "code", "message")
            }
            return RoomResult.fail(
                str(res.get("code") or "unknown"),
                str(res.get("message") or ""),
                **extra,
            )
        return RoomResult(ok=True, room=room, data=dict(res))

    async def _state(self, principal: Principal, code: str) -> Room | None:
        path = self.endpoints.state.format(code=code)
        res = await self._request("GET", path, principal=principal)
        if res.get("error"):
            return None
        return self._parse_room(res)

    # --- контракт ------------------------------------------------------------

    async def create_room(self, principal: Principal, draft: RoomDraft) -> RoomResult:
        password = draft.password if draft.password not in (None, "") else None
        body: dict[str, Any] = {
            "name": draft.name,
            "max_players": draft.max_players,
            "is_private": bool(draft.is_private or password),
        }
        if password is not None:
            body["password"] = password
        if draft.settings:
            body["settings"] = dict(draft.settings)
        body.update(dict(draft.extra))
        res = await self._request(
            "POST", self.endpoints.create, principal=principal, json=body
        )
        if res.get("error"):
            return self._result(res)
        code = str(res.get("code") or (res.get("room") or {}).get("code") or "")
        room = self._parse_room(res.get("room") or res)
        if room is None or not room.members:
            fetched = await self._state(principal, code) if code else None
            if fetched is not None:
                room = fetched
        if room is None:
            room = Room(
                code=code,
                name=draft.name,
                owner_id=principal.player_id,
                is_private=bool(draft.is_private or password),
                has_password=password is not None,
                max_players=draft.max_players,
                members=[
                    Member(
                        player_id=principal.player_id,
                        display_name=principal.display_name,
                    )
                ],
                settings=dict(draft.settings),
            )
        room.name = room.name or draft.name
        room.code = room.code or code
        return self._result(res, room)

    async def join_room(
        self, principal: Principal, code: str, password: str | None = None
    ) -> RoomResult:
        code = (code or "").strip().upper()
        body: dict[str, Any] = {}
        if password is not None:
            body["password"] = password
        path = self.endpoints.join.format(code=code)
        res = await self._request("POST", path, principal=principal, json=body)
        if res.get("error"):
            return self._result(res)
        joined_code = str(res.get("code") or code)
        room = self._parse_room(res.get("room") or res)
        if room is None or not room.members:
            fetched = await self._state(principal, joined_code)
            if fetched is not None:
                room = fetched
        if room is None:
            room = Room(code=joined_code, name="", owner_id="")
        room.code = room.code or joined_code
        return self._result(res, room)

    async def leave_room(self, principal: Principal, code: str) -> RoomResult:
        path = self.endpoints.leave.format(code=code)
        return self._result(await self._request("POST", path, principal=principal))

    async def disband_room(self, principal: Principal, code: str) -> RoomResult:
        path = self.endpoints.disband.format(code=code)
        return self._result(await self._request("POST", path, principal=principal))

    async def get_room(self, principal: Principal, code: str) -> Room | None:
        return await self._state(principal, code)

    async def list_rooms(
        self,
        principal: Principal,
        limit: int,
        offset: int,
        statuses: frozenset[str] | set[str] | None = None,
    ) -> tuple[list[Room], int]:
        path = self.endpoints.list.format(limit=int(limit), offset=int(offset))
        res = await self._request("GET", path, principal=principal)
        if res.get("error"):
            return [], 0
        items = []
        for raw in res.get("items") or []:
            room = self._parse_room(raw)
            if room is not None:
                items.append(room)
        try:
            total = int(res.get("total") or len(items))
        except (TypeError, ValueError):
            total = len(items)
        return items, total

    async def get_blacklist(self, principal: Principal, code: str) -> list[str]:
        path = self.endpoints.blacklist.format(code=code)
        res = await self._request("GET", path, principal=principal)
        if res.get("error"):
            return []
        return [str(x) for x in (res.get("blacklist") or [])]

    async def check_blacklist(self, principal: Principal, code: str) -> bool:
        path = self.endpoints.check_blacklist.format(code=code)
        res = await self._request("GET", path, principal=principal)
        if res.get("error"):
            return False
        return bool(res.get("blacklisted"))

    async def kick(
        self, principal: Principal, code: str, target_player_id: str
    ) -> RoomResult:
        path = self.endpoints.kick.format(code=code)
        res = await self._request(
            "POST", path, principal=principal, json={"target_player_id": target_player_id}
        )
        return self._result(res)

    async def pardon(
        self, principal: Principal, code: str, target_player_id: str
    ) -> RoomResult:
        path = self.endpoints.pardon.format(code=code)
        res = await self._request(
            "POST", path, principal=principal, json={"target_player_id": target_player_id}
        )
        return self._result(res)

    async def update_settings(
        self, principal: Principal, code: str, settings: dict
    ) -> RoomResult:
        path = self.endpoints.settings.format(code=code)
        res = await self._request("POST", path, principal=principal, json=dict(settings))
        return self._result(res)

    async def set_password(
        self, principal: Principal, code: str, password: str | None
    ) -> RoomResult:
        path = self.endpoints.password.format(code=code)
        res = await self._request(
            "POST", path, principal=principal, json={"password": password}
        )
        return self._result(res)
