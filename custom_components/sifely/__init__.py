"""Sifely Smart Lock integration for Home Assistant."""

from __future__ import annotations

import logging
from datetime import datetime

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SifelyApiError, SifelyAuthError, SifelyClient
from .const import (
    ATTR_END_DATE,
    ATTR_PASSCODE,
    ATTR_PASSCODE_ID,
    ATTR_PASSCODE_NAME,
    ATTR_START_DATE,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    SERVICE_ADD_PASSCODE,
    SERVICE_CHANGE_PASSCODE,
    SERVICE_DELETE_PASSCODE,
    SERVICE_LIST_PASSCODES,
)
from .coordinator import SifelyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LOCK]

# ── Service schemas ──────────────────────────────────────────────────────────

_LOCK_ID_SCHEMA = vol.Schema({
    vol.Required("lock_id"): vol.Coerce(int),
})

ADD_PASSCODE_SCHEMA = vol.Schema({
    vol.Required("lock_id"):       vol.Coerce(int),
    vol.Required(ATTR_PASSCODE):   cv.string,
    vol.Required(ATTR_PASSCODE_NAME): cv.string,
    vol.Optional(ATTR_START_DATE): vol.Coerce(int),  # ms timestamp; omit = now
    vol.Optional(ATTR_END_DATE):   vol.Coerce(int),  # ms timestamp; omit = permanent
})

CHANGE_PASSCODE_SCHEMA = vol.Schema({
    vol.Required("lock_id"):           vol.Coerce(int),
    vol.Required(ATTR_PASSCODE_ID):    vol.Coerce(int),
    vol.Optional(ATTR_PASSCODE):       cv.string,
    vol.Optional(ATTR_PASSCODE_NAME):  cv.string,
    vol.Optional(ATTR_START_DATE):     vol.Coerce(int),
    vol.Optional(ATTR_END_DATE):       vol.Coerce(int),
})

DELETE_PASSCODE_SCHEMA = vol.Schema({
    vol.Required("lock_id"):        vol.Coerce(int),
    vol.Required(ATTR_PASSCODE_ID): vol.Coerce(int),
})

LIST_PASSCODES_SCHEMA = vol.Schema({
    vol.Required("lock_id"): vol.Coerce(int),
})


def _now_ms() -> int:
    """Current time as a millisecond timestamp."""
    return int(datetime.now().timestamp() * 1000)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sifely from a config entry."""
    session = async_get_clientsession(hass)

    client = SifelyClient(
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data.get(CONF_CLIENT_SECRET, ""),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )

    if token_state := entry.data.get("token_state"):
        client.restore_token_state(token_state)

    try:
        await client.login()
    except SifelyAuthError as err:
        raise ConfigEntryAuthFailed(f"Invalid Sifely credentials: {err}") from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(f"Cannot connect to Sifely API: {err}") from err

    coordinator = SifelyDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ── Register passcode services ───────────────────────────────────────────

    async def handle_add_passcode(call: ServiceCall) -> None:
        """sifely.add_passcode — create a new passcode on a lock."""
        lock_id  = call.data["lock_id"]
        start_ms = call.data.get(ATTR_START_DATE, _now_ms())
        end_ms   = call.data.get(ATTR_END_DATE, 0)  # 0 = permanent

        try:
            result = await client.add_passcode(
                lock_id=lock_id,
                passcode=call.data[ATTR_PASSCODE],
                name=call.data[ATTR_PASSCODE_NAME],
                start_date=start_ms,
                end_date=end_ms,
            )
            _LOGGER.info(
                "Passcode '%s' added to lock %s (id=%s)",
                call.data[ATTR_PASSCODE_NAME],
                lock_id,
                result.get("keyboardPwdId"),
            )
            # Fire an event so automations / the UI can react
            hass.bus.async_fire(
                f"{DOMAIN}_passcode_added",
                {
                    "lock_id":        lock_id,
                    "passcode_id":    result.get("keyboardPwdId"),
                    "passcode":       result.get("keyboardPwd"),
                    "passcode_name":  call.data[ATTR_PASSCODE_NAME],
                },
            )
        except SifelyApiError as err:
            _LOGGER.error("Failed to add passcode to lock %s: %s", lock_id, err)

    async def handle_change_passcode(call: ServiceCall) -> None:
        """sifely.change_passcode — update an existing passcode."""
        lock_id     = call.data["lock_id"]
        passcode_id = call.data[ATTR_PASSCODE_ID]
        try:
            await client.change_passcode(
                lock_id=lock_id,
                passcode_id=passcode_id,
                new_passcode=call.data.get(ATTR_PASSCODE),
                new_name=call.data.get(ATTR_PASSCODE_NAME),
                start_date=call.data.get(ATTR_START_DATE),
                end_date=call.data.get(ATTR_END_DATE),
            )
            _LOGGER.info("Passcode %s on lock %s updated", passcode_id, lock_id)
            hass.bus.async_fire(
                f"{DOMAIN}_passcode_changed",
                {"lock_id": lock_id, "passcode_id": passcode_id},
            )
        except SifelyApiError as err:
            _LOGGER.error(
                "Failed to change passcode %s on lock %s: %s", passcode_id, lock_id, err
            )

    async def handle_delete_passcode(call: ServiceCall) -> None:
        """sifely.delete_passcode — remove a passcode from a lock."""
        lock_id     = call.data["lock_id"]
        passcode_id = call.data[ATTR_PASSCODE_ID]
        try:
            await client.delete_passcode(lock_id=lock_id, passcode_id=passcode_id)
            _LOGGER.info("Passcode %s deleted from lock %s", passcode_id, lock_id)
            hass.bus.async_fire(
                f"{DOMAIN}_passcode_deleted",
                {"lock_id": lock_id, "passcode_id": passcode_id},
            )
        except SifelyApiError as err:
            _LOGGER.error(
                "Failed to delete passcode %s from lock %s: %s", passcode_id, lock_id, err
            )

    async def handle_list_passcodes(call: ServiceCall) -> None:
        """sifely.list_passcodes — log all passcodes for a lock.

        Results are written to the HA log at INFO level AND fired as a
        sifely_passcodes_listed event so automations can consume them.
        """
        lock_id = call.data["lock_id"]
        try:
            passcodes = await client.get_passcodes(lock_id=lock_id)
            _LOGGER.info("Passcodes for lock %s (%d total):", lock_id, len(passcodes))
            for pwd in passcodes:
                _LOGGER.info(
                    "  [%s] '%s' code=%s type=%s start=%s end=%s",
                    pwd.get("keyboardPwdId"),
                    pwd.get("keyboardPwdName", "(unnamed)"),
                    pwd.get("keyboardPwd"),
                    pwd.get("keyboardPwdType"),
                    pwd.get("startDate"),
                    pwd.get("endDate"),
                )
            hass.bus.async_fire(
                f"{DOMAIN}_passcodes_listed",
                {"lock_id": lock_id, "passcodes": passcodes},
            )
        except SifelyApiError as err:
            _LOGGER.error("Failed to list passcodes for lock %s: %s", lock_id, err)

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_PASSCODE,    handle_add_passcode,    ADD_PASSCODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CHANGE_PASSCODE, handle_change_passcode, CHANGE_PASSCODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_PASSCODE, handle_delete_passcode, DELETE_PASSCODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_LIST_PASSCODES,  handle_list_passcodes,  LIST_PASSCODES_SCHEMA
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        for svc in (
            SERVICE_ADD_PASSCODE,
            SERVICE_CHANGE_PASSCODE,
            SERVICE_DELETE_PASSCODE,
            SERVICE_LIST_PASSCODES,
        ):
            hass.services.async_remove(DOMAIN, svc)
    return unload_ok
