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
    API_REFRESH_TOKEN,
    GRANT_TYPE_REFRESH,
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
    """Async client for the Sifely Smart Lock API.

    Authentication flow:
        1. POST /system/smart/login with client_id + username + md5(password)
           → returns access_token + refresh_token in response.data map
        2. Use "Bearer <access_token>" on all subsequent requests
        3. When token nears expiry, POST /system/smart/oauthToken with
           grant_type=refresh_token to get a new pair
    """

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
        """Perform a full username/password login and store tokens.

        The Sifely login endpoint returns tokens inside response.data as a
        flat string→string map:
            { "access_token": "...", "refresh_token": "...", "expires_in": "7200" }
        """
        params = {
            "client_id": self._client_id,
            "username":  self._username,
            "password":  self._password_md5,
        }
        _LOGGER.debug("Sifely login: client_id=%r username=%r", self._client_id, self._username)

        raw = await self._request("POST", API_LOGIN, params=params, auth=False)
        _LOGGER.debug("Sifely login raw response: %s", raw)

        # Top-level code field: 0 = success
        code = raw.get("code")
        if code != 0:
            raise SifelyAuthError(
                f"Login failed (code={code}): {raw.get('message', 'no message')}"
            )

        token_data: dict[str, str] = raw.get("data") or {}
        access  = token_data.get("access_token")
        refresh = token_data.get("refresh_token")
        try:
            expires_in = int(token_data.get("expires_in", 7200))
        except (TypeError, ValueError):
            expires_in = 7200

        if not access:
            raise SifelyAuthError(
                f"Login returned code=0 but no access_token. data={token_data}"
            )

        self._access_token      = access
        self._refresh_token     = refresh
        self._token_expires_at  = time.monotonic() + expires_in - 60
        _LOGGER.debug("Sifely login OK, token expires in %ds", expires_in)

    async def _refresh_access_token(self) -> None:
        """Use refresh_token to get a new access_token."""
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
            self._access_token     = data["access_token"]
            self._refresh_token    = data.get("refresh_token", self._refresh_token)
            expires_in             = int(data.get("expires_in", 7200))
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
            headers["Authorization"] = f"Bearer {self._access_token}"

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
                    raise SifelyAuthError("401 Unauthorized — credentials invalid or token expired")
                if resp.status == 403:
                    raise SifelyAuthError("403 Forbidden — check client_id and account permissions")
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

    # ── Commands ────────────────────────────────────────────────────────────

    async def unlock(self, lock_id: int) -> bool:
        data = await self._request("POST", API_LOCK_UNLOCK, params={"lockId": lock_id})
        return self._check_yes_or_not(data, "unlock")

    async def lock(self, lock_id: int) -> bool:
        data = await self._request("POST", API_LOCK_LOCK, params={"lockId": lock_id})
        return self._check_yes_or_not(data, "lock")

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

    # ── Gateway helpers ─────────────────────────────────────────────────────

    async def get_lock_gateways(self, lock_id: int) -> list[dict[str, Any]]:
        data = await self._request("GET", API_LOCK_GATEWAYS, params={"lockId": lock_id})
        return data.get("list", [])

    # ── Token persistence ───────────────────────────────────────────────────

    @property
    def token_state(self) -> dict[str, Any]:
        return {
            "access_token":      self._access_token,
            "refresh_token":     self._refresh_token,
            "token_expires_at":  self._token_expires_at,
        }

    def restore_token_state(self, state: dict[str, Any]) -> None:
        self._access_token     = state.get("access_token")
        self._refresh_token    = state.get("refresh_token")
        self._token_expires_at = float(state.get("token_expires_at", 0))
