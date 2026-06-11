"""Switch platform for Sifely — auto-lock and passage mode per lock."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import SifelyApiError, SifelyGatewayOfflineError
from .const import DOMAIN
from .coordinator import SifelyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Default auto-lock delay when turned on (seconds)
DEFAULT_AUTO_LOCK_SECONDS = 30


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sifely switch entities."""
    coordinator: SifelyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for lock_id in coordinator.data:
        entities.append(AutoLockSwitch(coordinator, lock_id))
        entities.append(PassageModeSwitch(coordinator, lock_id))
    async_add_entities(entities)


class _SifelySwitch(CoordinatorEntity[SifelyDataUpdateCoordinator], SwitchEntity):
    """Base class for Sifely switch entities."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator: SifelyDataUpdateCoordinator, lock_id: int) -> None:
        super().__init__(coordinator)
        self._lock_id = lock_id

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
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, str(self._lock_id))})

    @property
    def available(self) -> bool:
        return (self.coordinator.last_update_success
                and self._lock_id in self.coordinator.data)


class AutoLockSwitch(_SifelySwitch):
    """Switch to enable/disable auto-lock on a Sifely lock.

    When turned ON: sets auto-lock to DEFAULT_AUTO_LOCK_SECONDS (30 s).
    When turned OFF: sets auto-lock to 0 (disabled).
    The current auto-lock delay is shown as the 'delay_seconds' attribute.

    Note: Requires the lock's gateway to be online.
    """

    @property
    def unique_id(self) -> str:
        return f"sifely_autolock_{self._lock_id}"

    @property
    def name(self) -> str:
        return f"{self._lock_name} Auto-Lock"

    @property
    def icon(self) -> str:
        return "mdi:timer-lock" if self.is_on else "mdi:timer-lock-open"

    @property
    def is_on(self) -> bool | None:
        seconds = self._detail.get("autoLockTime")
        if seconds is None:
            return None
        return int(seconds) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"delay_seconds": self._detail.get("autoLockTime")}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable auto-lock with the default 30-second delay."""
        await self._set_auto_lock(DEFAULT_AUTO_LOCK_SECONDS)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable auto-lock."""
        await self._set_auto_lock(0)

    async def _set_auto_lock(self, seconds: int) -> None:
        try:
            await self.coordinator.client.set_auto_lock(self._lock_id, seconds)
            await self.coordinator.async_request_refresh()
        except SifelyGatewayOfflineError:
            _LOGGER.error("Cannot set auto-lock on %s: gateway offline", self._lock_name)
        except SifelyApiError as err:
            _LOGGER.error("Failed to set auto-lock on %s: %s", self._lock_name, err)


class PassageModeSwitch(_SifelySwitch):
    """Switch to enable/disable passage mode on a Sifely lock.

    Passage mode holds the lock in the unlocked state (useful for
    high-traffic periods or accessibility needs). When enabled via
    this switch it is configured as all-day, every day.

    Note: Requires the lock's gateway to be online.
    """

    @property
    def unique_id(self) -> str:
        return f"sifely_passagemode_{self._lock_id}"

    @property
    def name(self) -> str:
        return f"{self._lock_name} Passage Mode"

    @property
    def icon(self) -> str:
        return "mdi:door-open" if self.is_on else "mdi:door-closed-lock"

    @property
    def is_on(self) -> bool | None:
        pm = self._lock_data.get("passage_mode")
        if pm is None:
            # Fall back to detail field
            val = self._detail.get("passageMode")
            if val is None:
                return None
            return int(val) == 1
        # passageMode: 1=enabled, 2=disabled
        val = pm.get("passageMode")
        if val is None:
            return None
        return int(val) == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_passage_mode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_passage_mode(False)

    async def _set_passage_mode(self, enabled: bool) -> None:
        try:
            await self.coordinator.client.set_passage_mode(self._lock_id, enabled)
            await self.coordinator.async_request_refresh()
        except SifelyGatewayOfflineError:
            _LOGGER.error("Cannot set passage mode on %s: gateway offline", self._lock_name)
        except SifelyApiError as err:
            _LOGGER.error("Failed to set passage mode on %s: %s", self._lock_name, err)
