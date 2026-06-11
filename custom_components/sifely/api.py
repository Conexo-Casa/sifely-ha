"""Sifely API client for Home Assistant integration."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    API_GATEWAY_DETAILS,
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
    GRANT_TYPE_REFRESH,
    PWD_TYPE_PERMANENT,
    PWD_TYPE_TIMED,
    REMOTE_OP_TYPE,
    SIFELY_OK,
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
    """Async client for the Sifely Smart Lock API."""

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
        """Full username/password login.

        Live response shape:
            { "code": 200, "message": "Operation success!",
              "data": { "token": "...", "refreshToken": "...", "expires_in": "31536000" } }
        """
        params = {
            "client_id": self._client_id,
            "username":  self._username,
            "password":  self._password_md5,
        }
        _LOGGER.debug("Sifely login: client_id=%r username=%r", self._client_id, self._username)
        raw = await self._request("POST", API_LOGIN, params=params, auth=False)
        _LOGGER.debug("Sifely login response: %s", raw)

        code = raw.get("code")
        if code != SIFELY_OK:
            raise SifelyAuthError(
                f"Login failed (code={code}): {raw.get('message', 'no message')}"
            )

        data: dict[str, str] = raw.get("data") or {}
        access  = data.get("token")
        refresh = data.get("refreshToken")
        try:
            expires_in = int(data.get("expires_in", 7200))
        except (TypeError, ValueError):
            expires_in = 7200

        if not access:
            raise SifelyAuthError(f"Login returned code=200 but no token. data={data}")

        self._access_token     = access
        self._refresh_token    = refresh
        self._token_expires_at = time.monotonic() + expires_in - 60
        _LOGGER.debug("Sifely login OK, expires in %ds", expires_in)

    async def _refresh_access_token(self) -> None:
        if not self._refresh_token:
            _LOGGER.warning("No refresh token — performing full re-login")
            await self.login()
            return
        params = {
            "client_id":     self._client_id,
            "grant_type":    GRANT_TYPE_REFRESH,
            "refresh_token": self._refresh_token,
        }
        try:
            data = await self._request("POST", API_REFRESH_TOKEN, params=params, auth=False)
            access  = data.get("token") or data.get("access_token")
            refresh = data.get("refreshToken") or data.get("refresh_token")
            if not access:
                raise SifelyAuthError("No token in refresh response")
            self._access_token     = access
            self._refresh_token    = refresh or self._refresh_token
            try:
                expires_in = int(data.get("expires_in", 7200))
            except (TypeError, ValueError):
                expires_in = 7200
            self._token_expires_at = time.monotonic() + expires_in - 60
        except Exception:
            _LOGGER.warning("Token refresh failed — falling back to full login")
            await self.login()

    async def _ensure_token(self) -> None:
        async with self._token_lock:
            if not self._access_token or time.monotonic() >= self._token_expires_at:
                await self._refresh_access_token()

    # ── HTTP helper ─────────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        url = f"{API_BASE_URL}{path}"
        headers: dict[str, str] = {"Accept": "application/json"}

        if auth:
            await self._ensure_token()
            headers["Authorization"] = self._access_token  # type: ignore[assignment]

        try:
            async with self._session.request(
                method, url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                _LOGGER.debug("Sifely %s %s → HTTP %d", method, path, resp.status)
                if resp.status == 401:
                    raise SifelyAuthError("401 Unauthorized")
                if resp.status == 403:
                    raise SifelyAuthError("403 Forbidden")
                if resp.status == 404:
                    raise SifelyLockNotFoundError("404 Not Found")
                if resp.status >= 400:
                    text = await resp.text()
                    raise SifelyApiError(f"HTTP {resp.status}: {text[:200]}")
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise SifelyApiError(f"Network error: {err}") from err

    # ── Lock discovery ──────────────────────────────────────────────────────

    async def get_locks(self) -> list[dict[str, Any]]:
        locks: list[dict[str, Any]] = []
        page, page_size = 1, 20
        while True:
            data = await self._request(
                "POST", API_LOCK_LIST,
                params={"pageNo": str(page), "pageSize": str(page_size)},
            )
            page_locks: list[dict[str, Any]] = data.get("list", [])
            locks.extend(page_locks)
            if len(locks) >= data.get("total", 0) or not page_locks:
                break
            page += 1
        _LOGGER.debug("Fetched %d lock(s)", len(locks))
        return locks

    # ── Lock state ──────────────────────────────────────────────────────────

    async def get_lock_detail(self, lock_id: int) -> dict[str, Any]:
        return await self._request("GET", API_LOCK_DETAIL, params={"lockId": lock_id})

    async def get_lock_open_state(self, lock_id: int) -> int:
        data = await self._request("GET", API_LOCK_OPEN_STATE, params={"lockId": lock_id})
        return int(data.get("state", 2))

    # ── Lock / Unlock ────────────────────────────────────────────────────────

    async def unlock(self, lock_id: int) -> bool:
        data = await self._request("POST", API_LOCK_UNLOCK, params={"lockId": lock_id})
        return self._check_yes_or_not(data, "unlock")

    async def lock(self, lock_id: int) -> bool:
        data = await self._request("POST", API_LOCK_LOCK, params={"lockId": lock_id})
        return self._check_yes_or_not(data, "lock")

    # ── Passcode management ─────────────────────────────────────────────────

    async def get_passcodes(self, lock_id: int) -> list[dict[str, Any]]:
        """Return all passcodes for a lock.

        Response is a list of PwdListDTO:
            keyboardPwdId, keyboardPwd, keyboardPwdName,
            keyboardPwdType, startDate, endDate, senderUsername
        """
        data = await self._request(
            "GET", API_PASSCODE_LIST, params={"lockId": lock_id}
        )
        # API returns either a list directly or wrapped in data
        if isinstance(data, list):
            return data
        return data.get("list") or data.get("data") or []

    async def add_passcode(
        self,
        lock_id: int,
        passcode: str,
        name: str,
        start_date: int,
        end_date: int,
    ) -> dict[str, Any]:
        """Create a new passcode on a lock via the gateway.

        Args:
            lock_id:    Sifely lock ID.
            passcode:   The numeric passcode string (e.g. "123456").
            name:       A human-readable label (e.g. "Guest - Jane").
            start_date: Unix timestamp in milliseconds (0 = immediate).
            end_date:   Unix timestamp in milliseconds (0 = permanent).

        Returns:
            PwdAddDTO with keyboardPwdId and keyboardPwd.
        """
        pwd_type = PWD_TYPE_PERMANENT if end_date == 0 else PWD_TYPE_TIMED
        params: dict[str, Any] = {
            "lockId":          lock_id,
            "keyboardPwd":     passcode,
            "keyboardPwdName": name,
            "keyboardPwdType": pwd_type,
            "startDate":       start_date,
            "endDate":         end_date,
            "addType":         REMOTE_OP_TYPE,
        }
        result = await self._request("POST", API_PASSCODE_ADD, params=params)
        _LOGGER.debug("add_passcode result: %s", result)
        return result

    async def change_passcode(
        self,
        lock_id: int,
        passcode_id: int,
        new_passcode: str | None = None,
        new_name: str | None = None,
        start_date: int | None = None,
        end_date: int | None = None,
    ) -> bool:
        """Update an existing passcode (code, name, and/or validity dates).

        Only the fields you pass are changed; omit any field to leave it unchanged.
        """
        params: dict[str, Any] = {
            "lockId":        lock_id,
            "keyboardPwdId": passcode_id,
            "changeType":    REMOTE_OP_TYPE,
        }
        if new_passcode is not None:
            params["newKeyboardPwd"] = new_passcode
        if new_name is not None:
            params["keyboardPwdName"] = new_name
        if start_date is not None:
            params["startDate"] = start_date
        if end_date is not None:
            params["endDate"] = end_date

        result = await self._request("POST", API_PASSCODE_CHANGE, params=params)
        return self._check_yes_or_not(result, "change_passcode")

    async def delete_passcode(self, lock_id: int, passcode_id: int) -> bool:
        """Delete a passcode from a lock via the gateway."""
        params = {
            "lockId":        lock_id,
            "keyboardPwdId": passcode_id,
            "deleteType":    REMOTE_OP_TYPE,
        }
        result = await self._request("POST", API_PASSCODE_DELETE, params=params)
        return self._check_yes_or_not(result, "delete_passcode")

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _check_yes_or_not(self, data: dict[str, Any], op: str) -> bool:
        errcode = data.get("errcode", 0)
        errmsg  = data.get("errmsg", "")
        if errcode == 0:
            return True
        if "offline" in (errmsg or "").lower():
            raise SifelyGatewayOfflineError("Gateway offline — cannot operate lock remotely")
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

    # ── Token persistence ───────────────────────────────────────────────────

    @property
    def token_state(self) -> dict[str, Any]:
        return {
            "access_token":     self._access_token,
            "refresh_token":    self._refresh_token,
            "token_expires_at": self._token_expires_at,
        }

    def restore_token_state(self, state: dict[str, Any]) -> None:
        self._access_token     = state.get("access_token")
        self._refresh_token    = state.get("refresh_token")
        self._token_expires_at = float(state.get("token_expires_at", 0))
