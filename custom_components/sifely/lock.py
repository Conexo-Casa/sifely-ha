"""Sifely lock platform for Home Assistant.

Each Sifely lock in the account becomes a ``lock`` entity.  Remote
lock/unlock is only possible when the lock has a gateway online.

Entity state is polled from the Sifely cloud every 30 seconds via the
coordinator.  The entity also exposes key diagnostic attributes such as
battery level, firmware version, and gateway presence.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import SifelyApiError, SifelyGatewayOfflineError
from .const import (
    ATTR_AUTO_LOCK_TIME,
    ATTR_BATTERY,
    ATTR_FIRMWARE,
    ATTR_HAS_GATEWAY,
    ATTR_IS_FROZEN,
    ATTR_LOCK_ALIAS,
    ATTR_LOCK_ID,
    ATTR_LOCK_MAC,
    ATTR_LOCK_NAME,
    ATTR_REMOTE_ENABLED,
    DOMAIN,
    OPEN_STATE_LOCKED,
    OPEN_STATE_UNKNOWN,
    OPEN_STATE_UNLOCKED,
)
from .coordinator import SifelyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sifely lock entities from a config entry."""
    coordinator: SifelyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SifelyLockEntity(coordinator, lock_id)
        for lock_id in coordinator.data
    ]
    async_add_entities(entities)


class SifelyLockEntity(CoordinatorEntity[SifelyDataUpdateCoordinator], LockEntity):
    """Represents a single Sifely smart lock as a Home Assistant lock entity.

    State is sourced from the coordinator's polling data.  The entity
    supports lock and unlock operations via the Sifely gateway API.

    Attributes exposed as extra state attributes:
        - battery:          Battery level percentage.
        - lock_id:          Numeric Sifely lock ID.
        - lock_mac:         Bluetooth MAC address.
        - has_gateway:      Whether the lock is associated with a gateway.
        - firmware_revision: Installed firmware version string.
        - lock_alias:       User-assigned alias for the lock.
        - lock_name:        Factory name of the lock.
        - remote_enabled:   Whether remote unlock is enabled.
        - auto_lock_time:   Auto-lock timeout in seconds (0 = disabled).
        - is_frozen:        Whether the lock is in a frozen/disabled state.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SifelyDataUpdateCoordinator,
        lock_id: int,
    ) -> None:
        """Initialise the lock entity."""
        super().__init__(coordinator)
        self._lock_id = lock_id
        self._attr_unique_id = f"sifely_lock_{lock_id}"

    # ------------------------------------------------------------------
    # Properties derived from coordinator data
    # ------------------------------------------------------------------

    @property
    def _lock_data(self) -> dict[str, Any]:
        """Return the coordinator data slice for this lock."""
        return self.coordinator.data.get(self._lock_id, {})

    @property
    def _detail(self) -> dict[str, Any]:
        return self._lock_data.get("detail", {})

    @property
    def _key_info(self) -> dict[str, Any]:
        return self._lock_data.get("key_info", {})

    @property
    def name(self) -> str:
        """Return the entity name (shown in the UI)."""
        return (
            self._detail.get("lockAlias")
            or self._key_info.get("lockAlias")
            or self._detail.get("lockName")
            or f"Sifely Lock {self._lock_id}"
        )

    @property
    def is_locked(self) -> bool | None:
        """Return True if the lock reports itself as locked."""
        state = self._lock_data.get("open_state", OPEN_STATE_UNKNOWN)
        if state == OPEN_STATE_LOCKED:
            return True
        if state == OPEN_STATE_UNLOCKED:
            return False
        return None  # Unknown state

    @property
    def is_locking(self) -> bool:
        """Return True if the lock is in the process of locking."""
        return False  # Sifely API doesn't expose transitional states

    @property
    def is_unlocking(self) -> bool:
        """Return True if the lock is in the process of unlocking."""
        return False

    @property
    def is_jammed(self) -> bool | None:
        """Return True if the lock appears jammed (frozen)."""
        return bool(self._detail.get("isFrozen") == 1)

    @property
    def supported_features(self) -> LockEntityFeature:
        """Return features supported by this lock."""
        return LockEntityFeature(0)  # No open/close separation in Sifely API

    @property
    def available(self) -> bool:
        """Return True if the coordinator has data for this lock."""
        return (
            self.coordinator.last_update_success
            and self._lock_id in self.coordinator.data
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this lock."""
        detail = self._detail
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._lock_id))},
            name=self.name,
            manufacturer="Sifely",
            model=detail.get("lockName") or detail.get("lockAlias"),
            sw_version=detail.get("firmwareRevision"),
            hw_version=detail.get("hardwareRevision"),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes for diagnostics and automations."""
        detail = self._detail
        key_info = self._key_info
        return {
            ATTR_LOCK_ID: self._lock_id,
            ATTR_LOCK_MAC: detail.get("lockMac") or key_info.get("lockMac"),
            ATTR_BATTERY: detail.get("electricQuantity")
                or key_info.get("electricQuantity"),
            ATTR_HAS_GATEWAY: bool(
                (detail.get("hasGateway") or key_info.get("hasGateway")) == 1
            ),
            ATTR_FIRMWARE: detail.get("firmwareRevision"),
            ATTR_LOCK_ALIAS: detail.get("lockAlias") or key_info.get("lockAlias"),
            ATTR_LOCK_NAME: detail.get("lockName") or key_info.get("lockName"),
            ATTR_REMOTE_ENABLED: key_info.get("remoteEnable") == 1,
            ATTR_AUTO_LOCK_TIME: detail.get("autoLockTime"),
            ATTR_IS_FROZEN: detail.get("isFrozen") == 1,
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def async_lock(self, **kwargs: Any) -> None:
        """Send a lock command to the lock via the Sifely API."""
        _LOGGER.debug("Locking %s (lock_id=%s)", self.name, self._lock_id)
        try:
            await self.coordinator.client.lock(self._lock_id)
        except SifelyGatewayOfflineError:
            _LOGGER.error(
                "Cannot lock %s: gateway is offline. "
                "The lock must be within Bluetooth range of its gateway.",
                self.name,
            )
            return
        except SifelyApiError as err:
            _LOGGER.error("Error locking %s: %s", self.name, err)
            return

        # Request an immediate state refresh
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Send an unlock command to the lock via the Sifely API."""
        _LOGGER.debug("Unlocking %s (lock_id=%s)", self.name, self._lock_id)
        try:
            await self.coordinator.client.unlock(self._lock_id)
        except SifelyGatewayOfflineError:
            _LOGGER.error(
                "Cannot unlock %s: gateway is offline. "
                "The lock must be within Bluetooth range of its gateway.",
                self.name,
            )
            return
        except SifelyApiError as err:
            _LOGGER.error("Error unlocking %s: %s", self.name, err)
            return

        await self.coordinator.async_request_refresh()
