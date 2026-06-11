"""Sifely API client for Home Assistant integration."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    API_LOCK_DETAIL,
    API_LOCK_GATEWAYS,
    API_LOCK_LIST,
    API_LOCK_LOCK,
    API_LOCK_OPEN_STATE,
    API_LOCK_UNLOCK,
    API_LOGIN,
    API_PASSCODE_ADD,
    API_PASSCODE_CHANGE,
    API_PASSCODE_DELETE,
    API_PASSCODE_LIST,
    API_REFRESH_TOKEN,
    API_SET_AUTO_LOCK,
    API_GET_PASSAGE_MODE,
    API_SET_PASSAGE_MODE,
    API_UPDATE_SETTING,
    GRANT_TYPE_REFRESH,
    REMOTE_OP_TYPE,
    SIFELY_OK,
    SOUND_TYPE_VALUE,
)

_LOGGER = logging.getLogger(__name__)
REQUEST_TIMEOUT = 15


class SifelyAuthError(Exception):
    """Raised when authentication fails."""


class SifelyApiError(Exception):
    """Raised for general API errors."""


class SifelyLockNotFoundError(SifelyApiError):
    """Raised when the lock is not found."""


class SifelyGatewayOfflineError(SifelyApiError):
    """Raised when the gateway is offline."""


class SifelyClient:
    """Async client for the Sifely Smart Lock API (Sciener platform)."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._client_id     = client_id
        self._client_secret = client_secret
        self._username      = username
        self._password_md5  = hashlib.md5(password.encode()).hexdigest()
        self._session       = session

        self._access_token:  str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: float   = 0.0
        self._token_lock = asyncio.Lock()

    # ── Authentication ──────────────────────────────────────────────────────

    async def login(self) -> None:
        """Full username/password login."""
        params = {
            "client_id": self._client_id,
            "username":  self._username,
            "password":  self._password_md5,
        }
        raw = await self._request("POST", API_LOGIN, params=params, auth=False)
        code = raw.get("code")
        if code != SIFELY_OK:
            raise SifelyAuthError(f"Login failed (code={code}): {raw.get('message')}")
        data: dict = raw.get("data") or {}
        access  = data.get("token")
        refresh = data.get("refreshToken")
        expires_in = int(data.get("expires_in", 7200))
        if not access:
            raise SifelyAuthError(f"Login returned code=200 but no token. data={data}")
        self._access_token     = access
        self._refresh_token    = refresh
        self._token_expires_at = time.monotonic() + expires_in - 60

    async def _refresh_access_token(self) -> None:
        if not self._refresh_token:
            await self.login()
            return
        params = {"client_id": self._client_id, "grant_type": GRANT_TYPE_REFRESH,
                  "refresh_token": self._refresh_token}
        try:
            data = await self._request("POST", API_REFRESH_TOKEN, params=params, auth=False)
            access = data.get("token") or data.get("access_token")
            if not access:
                raise SifelyAuthError("No token in refresh response")
            self._access_token     = access
            self._refresh_token    = data.get("refreshToken") or data.get("refresh_token") or self._refresh_token
            self._token_expires_at = time.monotonic() + int(data.get("expires_in", 7200)) - 60
        except Exception:
            await self.login()

    async def _ensure_token(self) -> None:
        async with self._token_lock:
            if not self._access_token or time.monotonic() >= self._token_expires_at:
                await self._refresh_access_token()

    # ── HTTP ────────────────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        url = f"{API_BASE_URL}{path}"
        headers: dict[str, str] = {"Accept": "application/json"}
        if auth:
            await self._ensure_token()
            headers["Authorization"] = self._access_token  # type: ignore[assignment]
        try:
            async with self._session.request(
                method, url, params=params, data=data, headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status == 401:
                    raise SifelyAuthError("401 Unauthorized")
                if resp.status == 403:
                    raise SifelyAuthError("403 Forbidden")
                if resp.status == 404:
                    raise SifelyLockNotFoundError("404 Not Found")
                if resp.status >= 400:
                    raise SifelyApiError(f"HTTP {resp.status}: {await resp.text()[:200]}")
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise SifelyApiError(f"Network error: {err}") from err

    # ── Lock discovery ──────────────────────────────────────────────────────

    async def get_locks(self) -> list[dict[str, Any]]:
        locks: list[dict[str, Any]] = []
        page, page_size = 1, 20
        while True:
            data = await self._request("POST", API_LOCK_LIST,
                                       params={"pageNo": str(page), "pageSize": str(page_size)})
            page_locks = data.get("list", [])
            locks.extend(page_locks)
            if len(locks) >= data.get("total", 0) or not page_locks:
                break
            page += 1
        return locks

    async def get_lock_detail(self, lock_id: int) -> dict[str, Any]:
        return await self._request("GET", API_LOCK_DETAIL, params={"lockId": lock_id})

    async def get_lock_open_state(self, lock_id: int) -> int:
        data = await self._request("GET", API_LOCK_OPEN_STATE, params={"lockId": lock_id})
        return int(data.get("state", 2))

    # ── Lock / Unlock ────────────────────────────────────────────────────────

    async def unlock(self, lock_id: int) -> bool:
        return self._check_yon(await self._request("POST", API_LOCK_UNLOCK, params={"lockId": lock_id}), "unlock")

    async def lock(self, lock_id: int) -> bool:
        return self._check_yon(await self._request("POST", API_LOCK_LOCK, params={"lockId": lock_id}), "lock")

    # ── Passcodes ───────────────────────────────────────────────────────────

    async def get_passcodes(self, lock_id: int) -> list[dict[str, Any]]:
        data = await self._request("GET", API_PASSCODE_LIST, params={"lockId": lock_id})
        return data if isinstance(data, list) else (data.get("list") or data.get("data") or [])

    async def add_passcode(self, lock_id: int, passcode: str, name: str,
                           start_date: int, end_date: int) -> dict[str, Any]:
        from .const import PWD_TYPE_PERMANENT, PWD_TYPE_TIMED
        pwd_type = PWD_TYPE_PERMANENT if end_date == 0 else PWD_TYPE_TIMED
        return await self._request("POST", API_PASSCODE_ADD, params={
            "lockId": lock_id, "keyboardPwd": passcode, "keyboardPwdName": name,
            "keyboardPwdType": pwd_type, "startDate": start_date,
            "endDate": end_date, "addType": REMOTE_OP_TYPE,
        })

    async def change_passcode(self, lock_id: int, passcode_id: int,
                              new_passcode: str | None = None, new_name: str | None = None,
                              start_date: int | None = None, end_date: int | None = None) -> bool:
        params: dict[str, Any] = {"lockId": lock_id, "keyboardPwdId": passcode_id, "changeType": REMOTE_OP_TYPE}
        if new_passcode is not None: params["newKeyboardPwd"] = new_passcode
        if new_name is not None:     params["keyboardPwdName"] = new_name
        if start_date is not None:   params["startDate"] = start_date
        if end_date is not None:     params["endDate"] = end_date
        return self._check_yon(await self._request("POST", API_PASSCODE_CHANGE, params=params), "change_passcode")

    async def delete_passcode(self, lock_id: int, passcode_id: int) -> bool:
        return self._check_yon(await self._request("POST", API_PASSCODE_DELETE, params={
            "lockId": lock_id, "keyboardPwdId": passcode_id, "deleteType": REMOTE_OP_TYPE,
        }), "delete_passcode")

    # ── Lock settings ────────────────────────────────────────────────────────

    async def set_auto_lock(self, lock_id: int, seconds: int) -> bool:
        """Set auto-lock delay. 0 = disabled. Via gateway (type=2)."""
        return self._check_yon(await self._request("POST", API_SET_AUTO_LOCK, data={
            "lockId": lock_id, "seconds": seconds, "type": REMOTE_OP_TYPE,
        }), "set_auto_lock")

    async def set_sound_volume(self, lock_id: int, value: int) -> bool:
        """Set sound volume via lock/updateSetting (type=6).

        value: 0=off, 1=low, 2=medium-low, 3=medium, 4=medium-high, 5=high
        changeType=2 = via gateway.
        """
        return self._check_yon(await self._request("POST", API_UPDATE_SETTING, data={
            "lockId": lock_id, "type": SOUND_TYPE_VALUE, "value": value, "changeType": REMOTE_OP_TYPE,
        }), "set_sound_volume")

    async def get_passage_mode_config(self, lock_id: int) -> dict[str, Any]:
        """Fetch current passage mode configuration."""
        return await self._request("GET", API_GET_PASSAGE_MODE, params={"lockId": lock_id})

    async def set_passage_mode(self, lock_id: int, enabled: bool,
                               auto_unlock: bool = False) -> bool:
        """Enable or disable passage mode (all-day, all-week simple toggle).

        For Conexo Casa's accessibility use case: simple on/off.
        When enabled: all-day, every day of the week.
        """
        return self._check_yon(await self._request("POST", API_SET_PASSAGE_MODE, data={
            "lockId":      lock_id,
            "type":        REMOTE_OP_TYPE,
            "passageMode": 1 if enabled else 2,
            "autoUnlock":  1 if auto_unlock else 2,
            "isAllDay":    1,
            "startDate":   0,
            "endDate":     0,
            "weekDays":    json.dumps([1, 2, 3, 4, 5, 6, 7]),
        }), "set_passage_mode")

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _check_yon(self, data: dict[str, Any], op: str) -> bool:
        errcode = data.get("errcode", 0)
        errmsg  = data.get("errmsg", "")
        if errcode == 0:
            return True
        if "offline" in (errmsg or "").lower():
            raise SifelyGatewayOfflineError("Gateway offline")
        if errcode == -1003:
            raise SifelyLockNotFoundError("Lock does not exist")
        if errcode == -2025:
            raise SifelyApiError("Lock is frozen")
        if errcode == -4043:
            raise SifelyApiError("Feature not supported by this lock")
        raise SifelyApiError(f"Error {errcode} during {op}: {errmsg}")

    async def get_lock_gateways(self, lock_id: int) -> list[dict[str, Any]]:
        data = await self._request("GET", API_LOCK_GATEWAYS, params={"lockId": lock_id})
        return data.get("list", [])

    @property
    def token_state(self) -> dict[str, Any]:
        return {"access_token": self._access_token, "refresh_token": self._refresh_token,
                "token_expires_at": self._token_expires_at}

    def restore_token_state(self, state: dict[str, Any]) -> None:
        self._access_token     = state.get("access_token")
        self._refresh_token    = state.get("refresh_token")
        self._token_expires_at = float(state.get("token_expires_at", 0))
