"""Select platform for Sifely — sound volume per lock."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import SifelyApiError, SifelyGatewayOfflineError
from .const import DOMAIN, SOUND_VOLUME_LABELS, SOUND_VOLUME_OPTIONS
from .coordinator import SifelyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Human-readable option labels shown in the HA UI
SOUND_OPTION_LABELS = {
    "off":         "Off",
    "low":         "Low",
    "medium_low":  "Medium Low",
    "medium":      "Medium",
    "medium_high": "Medium High",
    "high":        "High",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sifely select entities."""
    coordinator: SifelyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        SoundVolumeSelect(coordinator, lock_id)
        for lock_id in coordinator.data
    ])


class SoundVolumeSelect(
    CoordinatorEntity[SifelyDataUpdateCoordinator], SelectEntity
):
    """Select entity for the lock's speaker volume.

    Options:  Off / Low / Medium Low / Medium / Medium High / High
    Maps to Sciener API values 0–5 via lock/updateSetting type=6.

    Note: Requires the lock's gateway to be online.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:volume-high"

    def __init__(
        self,
        coordinator: SifelyDataUpdateCoordinator,
        lock_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._lock_id = lock_id
        self._attr_options = list(SOUND_OPTION_LABELS.values())

    @property
    def unique_id(self) -> str:
        return f"sifely_sound_{self._lock_id}"

    @property
    def _lock_data(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._lock_id, {})

    @property
    def _detail(self) -> dict[str, Any]:
        return self._lock_data.get("detail", {})

    @property
    def _lock_name(self) -> str:
        return (self._detail.get("lockAlias")
                or self._lock_data.get("key_info", {}).get("lockAlias")
                or f"Lock {self._lock_id}")

    @property
    def name(self) -> str:
        return f"{self._lock_name} Sound Volume"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, str(self._lock_id))})

    @property
    def available(self) -> bool:
        return (self.coordinator.last_update_success
                and self._lock_id in self.coordinator.data)

    @property
    def current_option(self) -> str | None:
        """Return current volume level as a human-readable label."""
        raw = self._detail.get("soundVolume")
        if raw is None:
            return None
        key = SOUND_VOLUME_LABELS.get(int(raw))
        if key is None:
            return None
        return SOUND_OPTION_LABELS.get(key)

    async def async_select_option(self, option: str) -> None:
        """Change the sound volume level."""
        # Reverse-look up the API integer from the display label
        key = next((k for k, v in SOUND_OPTION_LABELS.items() if v == option), None)
        if key is None:
            _LOGGER.error("Unknown sound option: %s", option)
            return
        value = SOUND_VOLUME_OPTIONS[key]
        try:
            await self.coordinator.client.set_sound_volume(self._lock_id, value)
            await self.coordinator.async_request_refresh()
        except SifelyGatewayOfflineError:
            _LOGGER.error("Cannot set sound volume on %s: gateway offline", self._lock_name)
        except SifelyApiError as err:
            _LOGGER.error("Failed to set sound volume on %s: %s", self._lock_name, err)
