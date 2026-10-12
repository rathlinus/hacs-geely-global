"""Switches for the Geely EM integration.

State comes from the polled data, so after a command the switch follows
whatever the car reports on the next refresh.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.exceptions import HomeAssistantError

from . import GeelyEntity
from .api import GeelyEuClient
from .helpers import dig as _dig

# Climate side commands run for this many minutes, like the app's default.
DURATION = "15"


@dataclass(frozen=True)
class GeelySwitchDescription(SwitchEntityDescription):
    path: str = ""
    on_value: str = "1"
    # (client, vin, on) -> response
    send: Callable[[GeelyEuClient, str, bool], dict] = lambda c, vin, on: {}


def _env(key: str, level: str):
    def send(c: GeelyEuClient, vin: str, on: bool) -> dict:
        if not on:
            return c.environment(vin, [(key, "false")])
        return c.environment(
            vin, [(key, "true"), (f"{key}.level", level), (f"{key}.duration", DURATION)]
        )

    return send


SWITCHES: tuple[GeelySwitchDescription, ...] = (
    GeelySwitchDescription(
        key="charging_switch",
        name="Charging",
        icon="mdi:ev-station",
        path="status.additionalVehicleStatus.electricVehicleStatus.isCharging",
        send=lambda c, vin, on: c.charging(vin, on),
    ),
    GeelySwitchDescription(
        key="defrost",
        name="Defrost",
        icon="mdi:car-defrost-front",
        path="status.additionalVehicleStatus.climateStatus.defrost",
        send=_env("DF", "2"),
    ),
    GeelySwitchDescription(
        key="steering_wheel_heating",
        name="Steering wheel heating",
        icon="mdi:steering",
        path="status.additionalVehicleStatus.climateStatus.steerWhlHeatingSts",
        send=_env("SW", "3"),
    ),
    GeelySwitchDescription(
        key="parking_comfort_switch",
        name="Parking comfort",
        icon="mdi:car-seat",
        path="remoteState.parkingComfortState",
        send=lambda c, vin, on: c.remote_mode(vin, "1", on),
    ),
    GeelySwitchDescription(
        key="camping_mode_switch",
        name="Camping mode",
        icon="mdi:tent",
        path="remoteState.campingModeState",
        send=lambda c, vin, on: c.remote_mode(vin, "8", on),
    ),
    GeelySwitchDescription(
        key="sentry_mode_switch",
        name="Sentry mode",
        icon="mdi:cctv",
        path="remoteState.vstdModeState",
        send=lambda c, vin, on: c.remote_mode(vin, "6", on),
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["geely_em"][entry.entry_id]
    entities: list[SwitchEntity] = []
    for vin in coordinator.client.vins:
        vehicle = next((v for v in coordinator.client.vehicles if v.get("vin") == vin), {})
        for desc in SWITCHES:
            entities.append(GeelySwitch(coordinator, vin, vehicle, desc))
        for slot in (0, 1):
            entities.append(GeelyChargeSlotSwitch(coordinator, vin, vehicle, slot))
    async_add_entities(entities)


class GeelySwitch(GeelyEntity, SwitchEntity):
    entity_description: GeelySwitchDescription

    def __init__(self, coordinator, vin, vehicle, description):
        super().__init__(coordinator, vin, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{vin}_{description.key}"
        self._attr_device_info = self.device_info

    @property
    def is_on(self) -> bool | None:
        raw = _dig(self.coordinator.data or {}, f"{self.vin}.{self.entity_description.path}")
        if raw is None or raw == "":
            return None
        if isinstance(raw, bool):
            return raw
        return str(raw).lower() in (self.entity_description.on_value, "true")

    async def _set(self, on: bool) -> None:
        client = self.coordinator.client
        await self._send(lambda vin: self.entity_description.send(client, vin, on))

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)


def booking_payload(booking: dict, slot: int, **changes) -> tuple[bool, list[dict]]:
    """Copy all scheduled charging slots, changing only ``slot``. The app
    always sends the full list."""
    settings = []
    for i, s in enumerate(booking.get("settings") or []):
        item = {
            "id": s.get("id", i + 1),
            "sts": int(s.get("sts") or 0),
            "startTime": s.get("startTime") or "",
            "endTime": s.get("endTime") or "",
        }
        if i == slot:
            item.update(changes)
        settings.append(item)
    if slot >= len(settings):
        raise HomeAssistantError(f"the car reports no charging schedule slot {slot + 1}")
    return bool(booking.get("priorityToSoc")), settings


class GeelyChargeSlotSwitch(GeelyEntity, SwitchEntity):
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, vin, vehicle, slot: int):
        super().__init__(coordinator, vin, vehicle)
        self.slot = slot
        self._attr_name = f"Scheduled charging {slot + 1}"
        self._attr_unique_id = f"{vin}_booking_charge_{slot + 1}"
        self._attr_device_info = self.device_info

    @property
    def is_on(self) -> bool | None:
        raw = _dig(self._section("bookingCharge") or {}, f"settings.{self.slot}.sts")
        if raw is None or raw == "":
            return None
        return str(raw) == "1"

    async def _set(self, on: bool) -> None:
        priority, settings = booking_payload(
            self._section("bookingCharge") or {}, self.slot, sts=1 if on else 0
        )
        client = self.coordinator.client
        await self._send(lambda vin: client.set_booking_charge(vin, priority, settings))

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)
