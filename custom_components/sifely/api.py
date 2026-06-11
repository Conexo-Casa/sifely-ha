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
    """Raised when the gateway is offline (cannot remote-operate lock)."""


class SifelyClient:
    """Async client for the Sifely Smart Lock API.

    Handles authentication (login + token refresh), lock discovery,
    state polling, and lock/unlock commands.
    """

    def __init__(
        self,
        client_id: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialise the client with credentials and a shared aiohttp session."""
        self._client_id = client_id
        self._username = username
        self._password_md5 = hashlib.md5(password.encode()).hexdigest()
        self._session = session

        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def login(self) -> None:
        """Perform a full username/password login and store tokens."""
        params = {
            "client_id": self._client_id,
            "username": self._username,
            "password": self._password_md5,
        }
        _LOGGER.debug("Logging in as %s", self._username)
        data = await self._request("POST", API_LOGIN, params=params, auth=False)

        token_data: dict[str, str] = data.get("data", {})
        access = token_data.get("access_token")
        refresh = token_data.get("refresh_token")
        expires_in = int(token_data.get("expires_in", 7200))

        if not access:
            raise SifelyAuthError("Login succeeded but no access_token returned")

        self._access_token = access
        self._refresh_token = refresh
        self._token_expires_at = time.monotonic() + expires_in - 60  # 60 s margin

    async def _refresh_access_token(self) -> None:
        """Use the refresh_token to obtain a new access_token."""
        if not self._refresh_token:
            _LOGGER.warning("No refresh token available; performing full re-login")
            await self.login()
            return

        params = {
            "client_id": self._client_id,
            "grant_type": GRANT_TYPE_REFRESH,
            "refresh_token": self._refresh_token,
        }
        _LOGGER.debug("Refreshing access token")
        try:
            data = await self._request(
                "POST", API_REFRESH_TOKEN, params=params, auth=False
            )
            self._access_token = data["access_token"]
            self._refresh_token = data.get("refresh_token", self._refresh_token)
            expires_in = int(data.get("expires_in", 7200))
            self._token_expires_at = time.monotonic() + expires_in - 60
        except Exception:
            _LOGGER.warning("Token refresh failed; falling back to full login")
            await self.login()

    async def _ensure_token(self) -> None:
        """Ensure a valid access token exists, refreshing or re-logging if needed."""
        async with self._token_lock:
            if not self._access_token or time.monotonic() >= self._token_expires_at:
                await self._refresh_access_token()

    # ------------------------------------------------------------------
    # Low-level HTTP helper
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        """Make an authenticated HTTP request to the Sifely API.

        Args:
            method: HTTP method (GET, POST).
            path:   API path (e.g. '/v3/lock/detail').
            params: Query-string parameters.
            json_body: JSON request body (for POST requests with body).
            auth:   Whether to include the Authorization header.

        Returns:
            Parsed JSON response body as a dict.

        Raises:
            SifelyAuthError: On 401/403 responses.
            SifelyApiError:  On other error responses or network problems.
        """
        url = f"{API_BASE_URL}{path}"
        headers: dict[str, str] = {"Accept": "application/json"}

        if auth:
            await self._ensure_token()
            headers["Authorization"] = f"Bearer {self._access_token}"

        try:
            async with self._session.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status == 401:
                    raise SifelyAuthError("Unauthorized – credentials may be invalid")
                if resp.status == 403:
                    raise SifelyAuthError("Forbidden – check client_id and permissions")
                if resp.status == 404:
                    raise SifelyLockNotFoundError("Resource not found")
                if resp.status >= 400:
                    text = await resp.text()
                    raise SifelyApiError(
                        f"HTTP {resp.status} from Sifely API: {text[:200]}"
                    )
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise SifelyApiError(f"Network error contacting Sifely API: {err}") from err

    # ------------------------------------------------------------------
    # Lock discovery
    # ------------------------------------------------------------------

    async def get_locks(self) -> list[dict[str, Any]]:
        """Fetch the full list of locks owned by the authenticated account.

        Handles pagination automatically; returns a flat list of KeyInfo dicts.
        """
        locks: list[dict[str, Any]] = []
        page = 1
        page_size = 20

        while True:
            data = await self._request(
                "POST",
                API_LOCK_LIST,
                params={"pageNo": str(page), "pageSize": str(page_size)},
            )
            page_locks: list[dict[str, Any]] = data.get("list", [])
            locks.extend(page_locks)

            total: int = data.get("total", 0)
            if len(locks) >= total or not page_locks:
                break
            page += 1

        _LOGGER.debug("Fetched %d lock(s)", len(locks))
        return locks

    # ------------------------------------------------------------------
    # Lock state
    # ------------------------------------------------------------------

    async def get_lock_detail(self, lock_id: int) -> dict[str, Any]:
        """Return detailed information for a single lock (LockDetailDTO)."""
        return await self._request(
            "GET", API_LOCK_DETAIL, params={"lockId": lock_id}
        )

    async def get_lock_open_state(self, lock_id: int) -> int:
        """Return the open/close state of the lock.

        Returns:
            0 = locked, 1 = unlocked, 2 = unknown.
        """
        data = await self._request(
            "GET", API_LOCK_OPEN_STATE, params={"lockId": lock_id}
        )
        return int(data.get("state", 2))

    # ------------------------------------------------------------------
    # Lock / Unlock commands
    # ------------------------------------------------------------------

    async def unlock(self, lock_id: int) -> bool:
        """Send an unlock command to the lock via its gateway.

        Returns True on success, raises on failure.
        """
        data = await self._request(
            "POST", API_LOCK_UNLOCK, params={"lockId": lock_id}
        )
        return self._check_yes_or_not(data, "unlock")

    async def lock(self, lock_id: int) -> bool:
        """Send a lock command to the lock via its gateway.

        Returns True on success, raises on failure.
        """
        data = await self._request(
            "POST", API_LOCK_LOCK, params={"lockId": lock_id}
        )
        return self._check_yes_or_not(data, "lock")

    def _check_yes_or_not(self, data: dict[str, Any], op: str) -> bool:
        """Parse a YesOrNotDTO response and raise on error."""
        errcode = data.get("errcode", 0)
        errmsg = data.get("errmsg", "")

        if errcode == 0:
            return True

        # Map known error codes to meaningful exceptions
        if "offline" in (errmsg or "").lower():
            raise SifelyGatewayOfflineError(
                f"Gateway is offline – cannot {op} remotely"
            )
        if errcode == -1003:
            raise SifelyLockNotFoundError("Lock does not exist")
        if errcode == -2025:
            raise SifelyApiError("Lock is frozen and cannot be operated")
        if errcode == -4043:
            raise SifelyApiError("This feature is not supported by the lock")

        raise SifelyApiError(
            f"Sifely API returned error {errcode} during {op}: {errmsg}"
        )

    # ------------------------------------------------------------------
    # Gateway helpers
    # ------------------------------------------------------------------

    async def get_lock_gateways(self, lock_id: int) -> list[dict[str, Any]]:
        """Return the list of gateways associated with a lock."""
        data = await self._request(
            "GET", API_LOCK_GATEWAYS, params={"lockId": lock_id}
        )
        return data.get("list", [])

    async def get_gateway_detail(self, gateway_id: int) -> dict[str, Any]:
        """Return details for a specific gateway (GatewayDetailDTO)."""
        return await self._request(
            "GET", API_GATEWAY_DETAILS, params={"gatewayId": gateway_id}
        )

    # ------------------------------------------------------------------
    # Token state (for config-entry persistence)
    # ------------------------------------------------------------------

    @property
    def token_state(self) -> dict[str, Any]:
        """Return the current token state for persistent storage."""
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "token_expires_at": self._token_expires_at,
        }

    def restore_token_state(self, state: dict[str, Any]) -> None:
        """Restore a previously-saved token state (avoids re-login on HA restart)."""
        self._access_token = state.get("access_token")
        self._refresh_token = state.get("refresh_token")
        self._token_expires_at = float(state.get("token_expires_at", 0))
