"""DataUpdateCoordinator for the Sifely integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SifelyApiError, SifelyAuthError, SifelyClient
from .const import DOMAIN, OPEN_STATE_UNKNOWN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SifelyDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls Sifely API for all lock state including settings.

    Data shape per lock_id:
    {
        "detail":       { ...LockDetailDTO... },
        "open_state":   0 | 1 | 2,
        "key_info":     { ...KeyInfo from list... },
        "passage_mode": { ...PassageModeConfig... } | None,
    }
    """

    def __init__(self, hass: HomeAssistant, client: SifelyClient) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN,
                         update_interval=timedelta(seconds=UPDATE_INTERVAL))
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            locks = await self.client.get_locks()
        except SifelyAuthError as err:
            raise UpdateFailed(f"Auth error: {err}") from err
        except SifelyApiError as err:
            raise UpdateFailed(f"API error: {err}") from err

        result: dict[str, Any] = {}
        for lock_info in locks:
            lock_id: int = lock_info["lockId"]
            try:
                detail     = await self.client.get_lock_detail(lock_id)
                open_state = await self.client.get_lock_open_state(lock_id)
            except SifelyApiError as err:
                _LOGGER.warning("Could not fetch state for lock %s: %s", lock_id, err)
                open_state = OPEN_STATE_UNKNOWN
                detail     = lock_info

            # Fetch passage mode config (best-effort)
            try:
                passage_mode = await self.client.get_passage_mode_config(lock_id)
            except Exception:
                passage_mode = None

            result[lock_id] = {
                "detail":       detail,
                "open_state":   open_state,
                "key_info":     lock_info,
                "passage_mode": passage_mode,
            }
        return result
