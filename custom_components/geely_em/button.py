"""One-shot remote commands for the Geely EM integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription

from . import GeelyEntity
from .api import GeelyEuClient


@dataclass(frozen=True)
class GeelyButtonDescription(ButtonEntityDescription):
    # (client, vin) -> response
    press: Callable[[GeelyEuClient, str], dict] = lambda c, vin: {}


BUTTONS: tuple[GeelyButtonDescription, ...] = (
    GeelyButtonDescription(
        key="honk_flash",
        name="Honk and flash",
        icon="mdi:bullhorn",
        press=lambda c, vin: c.honk_flash(vin, "horn-light-flash"),
    ),
    GeelyButtonDescription(
        key="flash",
        name="Flash lights",
        icon="mdi:car-light-high",
        press=lambda c, vin: c.honk_flash(vin, "light-flash"),
    ),
    GeelyButtonDescription(
        key="unlock_trunk",
        name="Unlock trunk",
        icon="mdi:car-back",
        press=lambda c, vin: c.unlock_trunk(vin),
    ),
    GeelyButtonDescription(
        key="open_hood",
        name="Open front trunk",
        icon="mdi:car-select",
        press=lambda c, vin: c.open_hood(vin),
    ),
    GeelyButtonDescription(
        key="vent_windows",
        name="Vent windows",
        icon="mdi:window-open-variant",
        press=lambda c, vin: c.windows(vin, "ventilate", True),
    ),
    GeelyButtonDescription(
        key="close_windows",
        name="Close windows",
        icon="mdi:window-closed-variant",
        press=lambda c, vin: c.windows(vin, "window", False),
    ),
    GeelyButtonDescription(
        key="rapid_heat",
        name="Rapid heating",
        icon="mdi:sun-thermometer",
        press=lambda c, vin: c.smart_temp(vin, True, 28.5),
    ),
    GeelyButtonDescription(
        key="rapid_cool",
        name="Rapid cooling",
        icon="mdi:snowflake-thermometer",
        press=lambda c, vin: c.smart_temp(vin, False, 15.5),
    ),
    GeelyButtonDescription(
        key="locate",
        name="Update location",
        icon="mdi:crosshairs-gps",
        press=lambda c, vin: c.locate(vin),
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["geely_em"][entry.entry_id]
    entities = []
    for vin in coordinator.client.vins:
        vehicle = next((v for v in coordinator.client.vehicles if v.get("vin") == vin), {})
        for desc in BUTTONS:
            entities.append(GeelyButton(coordinator, vin, vehicle, desc))
    async_add_entities(entities)


class GeelyButton(GeelyEntity, ButtonEntity):
    entity_description: GeelyButtonDescription

    def __init__(self, coordinator, vin, vehicle, description):
        super().__init__(coordinator, vin, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{vin}_{description.key}"
        self._attr_device_info = self.device_info

    async def async_press(self) -> None:
        client = self.coordinator.client
        await self._send(lambda vin: self.entity_description.press(client, vin))
