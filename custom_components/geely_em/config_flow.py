"""Config flow for the Geely EM integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import GeelyApiError, GeelyAuthError, GeelyEuClient
from .const import CONF_COUNTRY, CONF_LANGUAGE, DEFAULT_COUNTRY, DEFAULT_LANGUAGE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required("email"): str,
        vol.Required("password"): str,
        vol.Required(CONF_COUNTRY, default=DEFAULT_COUNTRY): str,
        vol.Required(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): str,
    }
)


class GeelyHub:
    """Validate the credentials against the Geely EM backend."""

    def __init__(self, email: str, password: str, country: str, language: str) -> None:
        self.client = GeelyEuClient(email, password, country, language)

    def validate(self) -> list[dict]:
        self.client.login()
        return self.client.vehicle_list()


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> list[dict]:
    hub = GeelyHub(
        data["email"], data["password"], data[CONF_COUNTRY], data[CONF_LANGUAGE]
    )
    return await hass.async_add_executor_job(hub.validate)


class GeelyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                vehicles = await validate_input(self.hass, user_input)
            except GeelyAuthError:
                errors["base"] = "invalid_auth"
            except GeelyApiError as exc:
                _LOGGER.warning("Geely EM config flow API error: %s", exc)
                errors["base"] = "cannot_connect"
            except Exception as exc:  # noqa: BLE001
                _LOGGER.exception("Unexpected error in Geely EM config flow")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input["email"].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Geely ({user_input['email']})", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Failure to connect."""


class InvalidAuth(HomeAssistantError):
    """Invalid authentication."""
