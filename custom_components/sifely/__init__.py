"""Sifely Smart Lock integration for Home Assistant."""

from __future__ import annotations

import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SifelyAuthError, SifelyClient
from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)
from .coordinator import SifelyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LOCK]


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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
