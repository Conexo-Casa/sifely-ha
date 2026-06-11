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
    """Polls the Sifely API for all locks belonging to the account.

    Data structure returned by ``async_refresh``:
    ::

        {
            <lock_id_int>: {
                "detail":     { ...LockDetailDTO... },
                "open_state": 0 | 1 | 2,
            },
            ...
        }
    """

    def __init__(self, hass: HomeAssistant, client: SifelyClient) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest state for every lock in the account."""
        try:
            locks = await self.client.get_locks()
        except SifelyAuthError as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except SifelyApiError as err:
            raise UpdateFailed(f"Sifely API error: {err}") from err

        result: dict[str, Any] = {}

        for lock_info in locks:
            lock_id: int = lock_info["lockId"]
            try:
                detail = await self.client.get_lock_detail(lock_id)
                open_state = await self.client.get_lock_open_state(lock_id)
            except SifelyApiError as err:
                _LOGGER.warning(
                    "Could not fetch state for lock %s: %s", lock_id, err
                )
                open_state = OPEN_STATE_UNKNOWN
                detail = lock_info  # Fall back to list-level info

            result[lock_id] = {
                "detail": detail,
                "open_state": open_state,
                # Keep the original list-level fields for attributes
                "key_info": lock_info,
            }

        return result
