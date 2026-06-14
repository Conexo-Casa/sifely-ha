"""DataUpdateCoordinator for the Sifely integration.

API budget management
─────────────────────
Sifely allows 20,000 API calls per day (~833/hour, ~14/minute).

To stay well within budget we use a tiered polling strategy:

  Fast tier  (every 3 min) — lock open/close state only.
             1 call per lock per cycle.

  Slow tier  (every 30 min) — full detail refresh (battery, settings, etc.)
             + passage mode config.
             3 calls per lock per cycle.

  One-time   — lock list fetched once on startup, then only on HA restart
             or explicit reload. Locks rarely appear/disappear mid-session.

Budget at 3 locks:
  Fast:  (1 call × 3 locks) × (60/3 × 24) = 1,440 calls/day
  Slow:  (3 calls × 3 locks) × (60/30 × 24) = 432 calls/day
  Total: ~1,872 calls/day — well under the 20,000 limit.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SifelyApiError, SifelyAuthError, SifelyClient
from .const import DOMAIN, OPEN_STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)

# Fast cycle: state only (lock/unlock detection)
FAST_INTERVAL = timedelta(minutes=3)

# Slow cycle: full detail + passage mode (battery, settings)
SLOW_INTERVAL = timedelta(minutes=30)


class SifelyDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Tiered polling coordinator for Sifely locks.

    Data shape per lock_id::

        {
            "detail":       { ...LockDetailDTO... },
            "open_state":   0 | 1 | 2,
            "key_info":     { ...KeyInfo from list... },
            "passage_mode": { ...PassageModeConfig... } | None,
        }
    """

    def __init__(self, hass: HomeAssistant, client: SifelyClient) -> None:
        """Set up the fast-tier coordinator.

        The slow coordinator is a separate instance created alongside this one
        in async_setup_entry and shares the same data dict via _merge_slow_data.
        """
        super().__init__(
            hass, _LOGGER,
            name=f"{DOMAIN}_fast",
            update_interval=FAST_INTERVAL,
        )
        self.client = client
        self._lock_list: list[dict[str, Any]] = []
        # Slow-tier data keyed by lock_id; populated by SifelySlowCoordinator
        self._slow_data: dict[int, dict[str, Any]] = {}

    # ── Initial lock discovery ───────────────────────────────────────────────

    async def async_fetch_lock_list(self) -> None:
        """Fetch the lock list once (called at startup and on reload)."""
        try:
            self._lock_list = await self.client.get_locks()
            _LOGGER.debug("Sifely: fetched %d lock(s)", len(self._lock_list))
        except (SifelyAuthError, SifelyApiError) as err:
            raise UpdateFailed(f"Failed to fetch lock list: {err}") from err

    # ── Fast-tier: open state only ───────────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll open/close state for every lock — fast, cheap."""
        if not self._lock_list:
            await self.async_fetch_lock_list()

        result: dict[str, Any] = {}
        for lock_info in self._lock_list:
            lock_id: int = lock_info["lockId"]

            # Seed from slow-tier data so entities always have detail fields
            slow = self._slow_data.get(lock_id, {})
            result[lock_id] = {
                "detail":       slow.get("detail", lock_info),
                "key_info":     lock_info,
                "passage_mode": slow.get("passage_mode"),
                "open_state":   OPEN_STATE_UNKNOWN,
            }

            try:
                result[lock_id]["open_state"] = await self.client.get_lock_open_state(lock_id)
            except SifelyApiError as err:
                _LOGGER.warning("Could not poll state for lock %s: %s", lock_id, err)

        return result

    def merge_slow_data(self, lock_id: int, detail: dict, passage_mode: Any) -> None:
        """Called by the slow coordinator to inject detail data into fast state."""
        self._slow_data[lock_id] = {"detail": detail, "passage_mode": passage_mode}
        # Patch live data immediately so entities don't wait for next fast cycle
        if self.data and lock_id in self.data:
            self.data[lock_id]["detail"]       = detail
            self.data[lock_id]["passage_mode"] = passage_mode


class SifelySlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Slow-tier coordinator: full detail + passage mode, every 30 minutes."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SifelyClient,
        fast: SifelyDataUpdateCoordinator,
    ) -> None:
        super().__init__(
            hass, _LOGGER,
            name=f"{DOMAIN}_slow",
            update_interval=SLOW_INTERVAL,
        )
        self.client = client
        self._fast  = fast

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch full detail and passage mode for every lock."""
        result: dict[str, Any] = {}
        for lock_info in self._fast._lock_list:
            lock_id: int = lock_info["lockId"]
            detail = lock_info  # fallback

            try:
                detail = await self.client.get_lock_detail(lock_id)
            except SifelyApiError as err:
                _LOGGER.warning("Slow poll: detail failed for lock %s: %s", lock_id, err)

            passage_mode = None
            try:
                passage_mode = await self.client.get_passage_mode_config(lock_id)
            except SifelyApiError:
                pass

            result[lock_id] = {"detail": detail, "passage_mode": passage_mode}
            # Immediately share with the fast coordinator so entities update
            self._fast.merge_slow_data(lock_id, detail, passage_mode)

        return result
