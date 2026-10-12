"""Seat heating levels for the Geely EM integration (ZAF SH command)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity

from . import GeelyEntity
from .helpers import dig as _dig

DURATION = "15"
OPTIONS = ["off", "1", "2", "3"]

# (key, name, seat position code in the ZAF command, status field)
SEATS = (
    ("seat_heat_driver", "Seat heating driver", "11", "drvHeatSts"),
    ("seat_heat_passenger", "Seat heating passenger", "19", "passHeatingSts"),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["geely_em"][entry.entry_id]
    entities = []
    for vin in coordinator.client.vins:
        vehicle = next((v for v in coordinator.client.vehicles if v.get("vin") == vin), {})
        for seat in SEATS:
            entities.append(GeelySeatHeat(coordinator, vin, vehicle, *seat))
    async_add_entities(entities)


class GeelySeatHeat(GeelyEntity, SelectEntity):
    _attr_icon = "mdi:car-seat-heater"
    _attr_options = OPTIONS

    def __init__(self, coordinator, vin, vehicle, key, name, pos, field):
        super().__init__(coordinator, vin, vehicle)
        self.pos = pos
        self.field = field
        self._attr_name = name
        self._attr_unique_id = f"{vin}_{key}"
        self._attr_device_info = self.device_info

    @property
    def current_option(self) -> str | None:
        raw = _dig(self._status, f"additionalVehicleStatus.climateStatus.{self.field}")
        try:
            level = int(raw)
        except (TypeError, ValueError):
            return None
        return OPTIONS[level] if 0 <= level < len(OPTIONS) else None

    async def async_select_option(self, option: str) -> None:
        key = f"SH.{self.pos}"
        if option == "off":
            params = [(key, "false")]
        else:
            params = [(key, "true"), (f"{key}.level", option), (f"{key}.duration", DURATION)]
        client = self.coordinator.client
        await self._send(lambda vin: client.environment(vin, params))
