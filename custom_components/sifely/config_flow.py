"""Config flow for the Sifely Smart Lock integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SifelyAuthError, SifelyClient
from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID):     str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Required(CONF_USERNAME):      str,
        vol.Required(CONF_PASSWORD):      str,
    }
)


class SifelyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sifely Smart Lock.

    Field mapping:
        client_id     — "Your clientId" from the Sifely API portal
                        (e.g. "Conexo Casa")
        client_secret — "Your clientSecret" from the Sifely API portal
                        (e.g. "YqWgWWpZ5G/aXto8uharkA==")
        username      — Your Sifely *account* email or phone number
        password      — Your Sifely *account* password
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = SifelyClient(
                client_id=user_input[CONF_CLIENT_ID],
                client_secret=user_input[CONF_CLIENT_SECRET],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=session,
            )
            try:
                await client.login()
            except SifelyAuthError as err:
                _LOGGER.warning("Sifely auth error: %s", err)
                errors["base"] = "invalid_auth"
            except aiohttp.ClientError as err:
                _LOGGER.warning("Sifely connection error: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Sifely login")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_CLIENT_ID]}_{user_input[CONF_USERNAME]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Sifely ({user_input[CONF_USERNAME]})",
                    data={
                        CONF_CLIENT_ID:     user_input[CONF_CLIENT_ID],
                        CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
                        CONF_USERNAME:      user_input[CONF_USERNAME],
                        CONF_PASSWORD:      user_input[CONF_PASSWORD],
                        "token_state":      client.token_state,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication."""
        return await self.async_step_user(user_input)
