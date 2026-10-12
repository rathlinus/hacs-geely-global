"""The Geely EM integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import GeelyApiError, GeelyAuthError, GeelyEuClient
from .const import (
    CONF_COUNTRY,
    CONF_LANGUAGE,
    DEFAULT_COUNTRY,
    DEFAULT_LANGUAGE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "device_tracker", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    email = entry.data["email"]
    password = entry.data["password"]
    country = entry.data.get(CONF_COUNTRY, DEFAULT_COUNTRY)
    language = entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)

    client = GeelyEuClient(email, password, country, language)
    await hass.async_add_executor_job(client.login)
    await hass.async_add_executor_job(client.vehicle_list)

    coordinator = GeelyCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


class GeelyCoordinator(DataUpdateCoordinator):
    """Polls the vehicle status for all VINs of the account."""

    def __init__(self, hass: HomeAssistant, client: GeelyEuClient) -> None:
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    def _poll(self) -> dict:
        self.client.vehicle_list()
        out = {}
        for vin in self.client.vins:
            try:
                out[vin] = self.client.poll_vehicle(vin)
            except GeelyAuthError:
                _LOGGER.info("Geely EM: session expired, re-logging in")
                self.client.login()
                out[vin] = self.client.poll_vehicle(vin)
        return out

    async def _async_update_data(self) -> dict:
        try:
            async with async_timeout.timeout(90):
                return await self.hass.async_add_executor_job(self._poll)
        except GeelyAuthError as exc:
            raise UpdateFailed(f"Authentication failed: {exc}") from exc
        except GeelyApiError as exc:
            raise UpdateFailed(f"Geely API error: {exc}") from exc


class GeelyEntity(CoordinatorEntity[GeelyCoordinator]):
    """Base entity for Geely EM vehicles."""

    def __init__(self, coordinator: GeelyCoordinator, vin: str, vehicle: dict) -> None:
        super().__init__(coordinator)
        self.vin = vin
        self.vehicle = vehicle

    @property
    def _status(self) -> dict:
        return (self.coordinator.data or {}).get(self.vin, {}).get("status") or {}

    @property
    def _remote(self) -> dict:
        return (self.coordinator.data or {}).get(self.vin, {}).get("remoteState") or {}

    def _section(self, key: str) -> dict | list | None:
        return (self.coordinator.data or {}).get(self.vin, {}).get(key)

    @property
    def device_info(self):
        model = self.vehicle.get("appModelCode") or self.vehicle.get("nickName") or "Geely"
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": self.vehicle.get("nickName") or f"Geely {model}",
            "manufacturer": "Geely",
            "model": model,
            "serial_number": self.vin,
        }
