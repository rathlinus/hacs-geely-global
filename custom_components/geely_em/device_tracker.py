"""Device tracker for the Geely EM integration."""
from __future__ import annotations

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GeelyCoordinator
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: GeelyCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for vin in coordinator.client.vins:
        vehicle = next((v for v in coordinator.client.vehicles if v.get("vin") == vin), {})
        entities.append(GeelyTracker(coordinator, vin, vehicle))
    async_add_entities(entities)


class GeelyTracker(CoordinatorEntity, TrackerEntity):
    def __init__(self, coordinator: GeelyCoordinator, vin: str, vehicle: dict) -> None:
        super().__init__(coordinator)
        self.vin = vin
        self.vehicle = vehicle
        self._attr_unique_id = f"{vin}_tracker"
        self._attr_has_entity_name = True
        self._attr_name = "Location"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, vin)},
            "name": vehicle.get("nickName") or f"Geely {vehicle.get('appModelCode', '')}",
            "manufacturer": "Geely",
            "model": vehicle.get("appModelCode") or "Geely",
            "serial_number": vin,
        }

    @property
    def latitude(self) -> float | None:
        pos = (self._status or {}).get("basicVehicleStatus", {}).get("position") or {}
        try:
            return float(pos.get("latitude"))
        except (TypeError, ValueError):
            return None

    @property
    def longitude(self) -> float | None:
        pos = (self._status or {}).get("basicVehicleStatus", {}).get("position") or {}
        try:
            return float(pos.get("longitude"))
        except (TypeError, ValueError):
            return None

    @property
    def _status(self) -> dict:
        return (self.coordinator.data or {}).get(self.vin, {}).get("status") or {}

    @property
    def battery_level(self) -> int | None:
        try:
            return int(float(
                (self._status.get("additionalVehicleStatus", {})
                 .get("electricVehicleStatus", {}) or {}).get("chargeLevel") or 0
            ))
        except (TypeError, ValueError):
            return None

    @property
    def source_type(self) -> str:
        return "gps"

    @property
    def icon(self) -> str:
        return "mdi:car"
