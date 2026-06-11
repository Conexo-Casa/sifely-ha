"""Sifely Smart Lock integration for Home Assistant."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

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
    ATTR_END_DATE, ATTR_PASSCODE, ATTR_PASSCODE_ID, ATTR_PASSCODE_NAME, ATTR_START_DATE,
    CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_PASSWORD, CONF_USERNAME, DOMAIN,
    SERVICE_ADD_PASSCODE, SERVICE_CHANGE_PASSCODE, SERVICE_DELETE_PASSCODE, SERVICE_LIST_PASSCODES,
)
from .coordinator import SifelyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LOCK, Platform.SWITCH, Platform.SELECT]

# Lovelace card JS filename (served from /local/sifely/)
CARD_JS = "sifely-passcode-card.js"
RESOURCE_URL = f"/local/sifely/{CARD_JS}"

ADD_PASSCODE_SCHEMA = vol.Schema({
    vol.Required("lock_id"):          vol.Coerce(int),
    vol.Required(ATTR_PASSCODE):      cv.string,
    vol.Required(ATTR_PASSCODE_NAME): cv.string,
    vol.Optional(ATTR_START_DATE):    vol.Coerce(int),
    vol.Optional(ATTR_END_DATE):      vol.Coerce(int),
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
LIST_PASSCODES_SCHEMA = vol.Schema({vol.Required("lock_id"): vol.Coerce(int)})


def _now_ms() -> int:
    return int(datetime.now().timestamp() * 1000)


async def _install_lovelace_card(hass: HomeAssistant) -> None:
    """Copy the Lovelace card JS into www/sifely/ and register it as a resource.

    HA serves files from <config>/www/ at /local/. We copy the bundled JS there
    once on setup so the card is always in sync with the installed integration version.
    """
    # Source: bundled in custom_components/sifely/www/
    src = Path(__file__).parent / "www" / CARD_JS
    if not src.exists():
        _LOGGER.warning("Sifely card JS not found at %s — skipping resource install", src)
        return

    # Destination: <config>/www/sifely/
    dest_dir = Path(hass.config.config_dir) / "www" / "sifely"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / CARD_JS

    # Copy if missing or outdated
    try:
        if not dest.exists() or dest.read_bytes() != src.read_bytes():
            dest.write_bytes(src.read_bytes())
            _LOGGER.info("Sifely Lovelace card installed to %s", dest)
    except OSError as err:
        _LOGGER.warning("Could not copy Sifely card JS: %s", err)
        return

    # Register as a Lovelace resource (idempotent)
    try:
        resources = hass.data.get("lovelace", {}).get("resources")
        if resources is not None:
            existing = [r for r in await resources.async_get_info()
                        if r.get("url") == RESOURCE_URL]
            if not existing:
                await resources.async_create_item(
                    {"res_type": "module", "url": RESOURCE_URL}
                )
                _LOGGER.info("Registered Sifely Lovelace resource: %s", RESOURCE_URL)
    except Exception as err:
        # Non-fatal — user can register manually if needed
        _LOGGER.debug("Could not auto-register Lovelace resource: %s", err)


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

    # Install Lovelace card (best-effort, non-blocking)
    hass.async_create_task(_install_lovelace_card(hass))

    # ── Passcode services ────────────────────────────────────────────────────

    async def handle_add_passcode(call: ServiceCall) -> None:
        lock_id  = call.data["lock_id"]
        start_ms = call.data.get(ATTR_START_DATE, _now_ms())
        end_ms   = call.data.get(ATTR_END_DATE, 0)
        try:
            result = await client.add_passcode(
                lock_id, call.data[ATTR_PASSCODE],
                call.data[ATTR_PASSCODE_NAME], start_ms, end_ms)
            _LOGGER.info("Passcode '%s' added to lock %s (id=%s)",
                         call.data[ATTR_PASSCODE_NAME], lock_id, result.get("keyboardPwdId"))
            hass.bus.async_fire(f"{DOMAIN}_passcode_added", {
                "lock_id": lock_id,
                "passcode_id": result.get("keyboardPwdId"),
                "passcode": result.get("keyboardPwd"),
                "passcode_name": call.data[ATTR_PASSCODE_NAME],
            })
        except SifelyApiError as err:
            _LOGGER.error("Failed to add passcode to lock %s: %s", lock_id, err)

    async def handle_change_passcode(call: ServiceCall) -> None:
        lock_id = call.data["lock_id"]
        pid     = call.data[ATTR_PASSCODE_ID]
        try:
            await client.change_passcode(
                lock_id, pid,
                call.data.get(ATTR_PASSCODE),
                call.data.get(ATTR_PASSCODE_NAME),
                call.data.get(ATTR_START_DATE),
                call.data.get(ATTR_END_DATE))
            hass.bus.async_fire(f"{DOMAIN}_passcode_changed",
                                {"lock_id": lock_id, "passcode_id": pid})
        except SifelyApiError as err:
            _LOGGER.error("Failed to change passcode %s on lock %s: %s", pid, lock_id, err)

    async def handle_delete_passcode(call: ServiceCall) -> None:
        lock_id = call.data["lock_id"]
        pid     = call.data[ATTR_PASSCODE_ID]
        try:
            await client.delete_passcode(lock_id, pid)
            hass.bus.async_fire(f"{DOMAIN}_passcode_deleted",
                                {"lock_id": lock_id, "passcode_id": pid})
        except SifelyApiError as err:
            _LOGGER.error("Failed to delete passcode %s on lock %s: %s", pid, lock_id, err)

    async def handle_list_passcodes(call: ServiceCall) -> None:
        lock_id = call.data["lock_id"]
        try:
            passcodes = await client.get_passcodes(lock_id)
            _LOGGER.info("Passcodes for lock %s (%d):", lock_id, len(passcodes))
            for p in passcodes:
                _LOGGER.info("  [%s] '%s' code=%s type=%s start=%s end=%s",
                    p.get("keyboardPwdId"), p.get("keyboardPwdName", "(unnamed)"),
                    p.get("keyboardPwd"), p.get("keyboardPwdType"),
                    p.get("startDate"), p.get("endDate"))
            hass.bus.async_fire(f"{DOMAIN}_passcodes_listed",
                                {"lock_id": lock_id, "passcodes": passcodes})
        except SifelyApiError as err:
            _LOGGER.error("Failed to list passcodes for lock %s: %s", lock_id, err)

    hass.services.async_register(DOMAIN, SERVICE_ADD_PASSCODE,    handle_add_passcode,    ADD_PASSCODE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CHANGE_PASSCODE, handle_change_passcode, CHANGE_PASSCODE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_PASSCODE, handle_delete_passcode, DELETE_PASSCODE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_LIST_PASSCODES,  handle_list_passcodes,  LIST_PASSCODES_SCHEMA)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        for svc in (SERVICE_ADD_PASSCODE, SERVICE_CHANGE_PASSCODE,
                    SERVICE_DELETE_PASSCODE, SERVICE_LIST_PASSCODES):
            hass.services.async_remove(DOMAIN, svc)
    return unload_ok
