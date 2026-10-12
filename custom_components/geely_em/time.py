"""Scheduled charging window times for the Geely EM integration."""
from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity

from . import GeelyEntity
from .helpers import dig as _dig
from .switch import booking_payload


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["geely_em"][entry.entry_id]
    entities = []
    for vin in coordinator.client.vins:
        vehicle = next((v for v in coordinator.client.vehicles if v.get("vin") == vin), {})
        for slot in (0, 1):
            for field in ("startTime", "endTime"):
                entities.append(GeelyChargeTime(coordinator, vin, vehicle, slot, field))
    async_add_entities(entities)


def _parse(raw) -> time | None:
    if not raw:
        return None
    try:
        parts = [int(p) for p in str(raw).split(":")]
        return time(*parts[:3])
    except (TypeError, ValueError):
        return None


class GeelyChargeTime(GeelyEntity, TimeEntity):
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, vin, vehicle, slot: int, field: str):
        super().__init__(coordinator, vin, vehicle)
        self.slot = slot
        self.field = field
        label = "start" if field == "startTime" else "end"
        self._attr_name = f"Scheduled charging {slot + 1} {label}"
        self._attr_unique_id = f"{vin}_booking_charge_{slot + 1}_{label}"
        self._attr_device_info = self.device_info

    @property
    def _raw(self):
        return _dig(self._section("bookingCharge") or {}, f"settings.{self.slot}.{self.field}")

    @property
    def native_value(self) -> time | None:
        return _parse(self._raw)

    async def async_set_value(self, value: time) -> None:
        # Keep the format the car uses (HH:MM or HH:MM:SS).
        fmt = "%H:%M:%S" if str(self._raw or "").count(":") == 2 else "%H:%M"
        priority, settings = booking_payload(
            self._section("bookingCharge") or {}, self.slot, **{self.field: value.strftime(fmt)}
        )
        client = self.coordinator.client
        await self._send(lambda vin: client.set_booking_charge(vin, priority, settings))
