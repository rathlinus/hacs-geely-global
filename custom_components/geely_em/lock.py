"""Door lock for the Geely EM integration."""
from __future__ import annotations

from homeassistant.components.lock import LockEntity

from . import GeelyEntity
from .helpers import dig as _dig


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["geely_em"][entry.entry_id]
    entities = []
    for vin in coordinator.client.vins:
        vehicle = next((v for v in coordinator.client.vehicles if v.get("vin") == vin), {})
        entities.append(GeelyLock(coordinator, vin, vehicle))
    async_add_entities(entities)


class GeelyLock(GeelyEntity, LockEntity):
    _attr_name = "Doors"

    def __init__(self, coordinator, vin, vehicle):
        super().__init__(coordinator, vin, vehicle)
        self._attr_unique_id = f"{vin}_door_lock"
        self._attr_device_info = self.device_info

    @property
    def is_locked(self) -> bool | None:
        raw = _dig(
            self._status, "additionalVehicleStatus.drivingSafetyStatus.centralLockingStatus"
        )
        if raw in (None, ""):
            return None
        return str(raw) == "1"

    async def async_lock(self, **kwargs) -> None:
        await self._send(self.coordinator.client.lock)

    async def async_unlock(self, **kwargs) -> None:
        await self._send(self.coordinator.client.unlock)
