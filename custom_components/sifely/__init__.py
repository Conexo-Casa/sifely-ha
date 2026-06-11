"""Sifely Smart Lock integration for Home Assistant.

This integration connects to the Sifely cloud API to expose each Sifely
smart lock as a Home Assistant ``lock`` entity.  Authentication uses the
Sifely OAuth 2.0 flow (username + password + client credentials).

Platforms registered:
    - lock   – one entity per lock in the Sifely account

Services:
    - sifely.lock   – lock a specific lock
    - sifely.unlock – unlock a specific lock (gateway must be online)
"""

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
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)
from .coordinator import SifelyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LOCK]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sifely from a config entry.

    Called by Home Assistant when the user completes the config flow, or
    when HA starts and the entry already exists.
    """
    session = async_get_clientsession(hass)

    client = SifelyClient(
        client_id=entry.data[CONF_CLIENT_ID],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )

    # Restore saved tokens to avoid an unnecessary re-login on every HA restart
    if token_state := entry.data.get("token_state"):
        client.restore_token_state(token_state)

    try:
        await client.login()
    except SifelyAuthError as err:
        raise ConfigEntryAuthFailed(
            f"Invalid credentials for Sifely account: {err}"
        ) from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to Sifely API: {err}"
        ) from err

    coordinator = SifelyDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and clean up resources."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
