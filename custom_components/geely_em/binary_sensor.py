"""Binary sensors for the Geely EM integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from . import GeelyEntity
from .helpers import dig as _dig


@dataclass(frozen=True)
class GeelyBinaryDescription(BinarySensorEntityDescription):
    path: str = ""
    inverted: bool = False


BINARY_SENSORS: tuple[GeelyBinaryDescription, ...] = (
    # --- charging ---
    GeelyBinaryDescription(
        key="charging",
        name="Charging",
        path="status.additionalVehicleStatus.electricVehicleStatus.isCharging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    GeelyBinaryDescription(
        key="plugged_in",
        name="Plugged in",
        path="status.additionalVehicleStatus.electricVehicleStatus.isPluggedIn",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    GeelyBinaryDescription(
        key="scheduled_charging_active",
        name="Scheduled charging active",
        path="chargingPlan.bcCycleActive",
        icon="mdi:calendar-clock",
    ),
    GeelyBinaryDescription(
        key="travel_plan_ac",
        name="Travel plan pre-climatization",
        path="travelPlan.ac",
        icon="mdi:air-conditioner",
    ),
    GeelyBinaryDescription(
        key="pre_climate_active",
        name="Pre-climatization active",
        path="status.additionalVehicleStatus.climateStatus.preClimateActive",
        icon="mdi:hvac",
    ),
    # --- locks / openings (OPENING: on = open) ---
    GeelyBinaryDescription(
        key="locked",
        name="Locked",
        path="status.additionalVehicleStatus.drivingSafetyStatus.centralLockingStatus",
        inverted=True,
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    GeelyBinaryDescription(
        key="trunk_open",
        name="Trunk",
        path="status.additionalVehicleStatus.drivingSafetyStatus.trunkOpenStatus",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    GeelyBinaryDescription(
        key="hood_open",
        name="Hood",
        path="status.additionalVehicleStatus.drivingSafetyStatus.engineHoodOpenStatus",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    GeelyBinaryDescription(
        key="door_driver",
        name="Door driver",
        path="status.additionalVehicleStatus.drivingSafetyStatus.doorOpenStatusDriver",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    GeelyBinaryDescription(
        key="door_passenger",
        name="Door passenger",
        path="status.additionalVehicleStatus.drivingSafetyStatus.doorOpenStatusPassenger",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    GeelyBinaryDescription(
        key="door_rear_left",
        name="Door rear left",
        path="status.additionalVehicleStatus.drivingSafetyStatus.doorOpenStatusDriverRear",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    GeelyBinaryDescription(
        key="door_rear_right",
        name="Door rear right",
        path="status.additionalVehicleStatus.drivingSafetyStatus.doorOpenStatusPassengerRear",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    GeelyBinaryDescription(
        key="sunroof_open",
        name="Sunroof",
        path="status.additionalVehicleStatus.climateStatus.sunroofOpenStatus",
        inverted=True,
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    # --- warnings ---
    GeelyBinaryDescription(
        key="tyre_warning",
        name="Tyre pressure warning",
        path="status.additionalVehicleStatus.maintenanceStatus.tyrePreWarningDriver",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    GeelyBinaryDescription(
        key="washer_fluid_low",
        name="Washer fluid low",
        path="status.additionalVehicleStatus.maintenanceStatus.washerFluidLevelStatus",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    # --- remote control modes (getVehicleState, 1 = on) ---
    GeelyBinaryDescription(
        key="parking_comfort",
        name="Parking comfort",
        path="remoteState.parkingComfortState",
        icon="mdi:car-seat",
    ),
    GeelyBinaryDescription(
        key="camping_mode",
        name="Camping mode",
        path="remoteState.campingModeState",
        icon="mdi:tent",
    ),
    GeelyBinaryDescription(
        key="stranger_mode",
        name="Stranger mode",
        path="remoteState.strangerModeState",
        icon="mdi:account-alert",
    ),
    GeelyBinaryDescription(
        key="overheat_protection",
        name="Overheat protection",
        path="remoteState.overheatState",
        icon="mdi:sun-thermometer",
    ),
    GeelyBinaryDescription(
        key="sentry_mode",
        name="Sentry mode",
        path="remoteState.vstdModeState",
        icon="mdi:cctv",
    ),
)


def _to_bool(raw: Any) -> bool | None:
    if raw is None or raw == "":
        return None
    try:
        return bool(int(raw))
    except (TypeError, ValueError):
        return bool(raw)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["geely_em"][entry.entry_id]
    entities = []
    for vin in coordinator.client.vins:
        vehicle = next((v for v in coordinator.client.vehicles if v.get("vin") == vin), {})
        for desc in BINARY_SENSORS:
            entities.append(GeelyBinarySensor(coordinator, vin, vehicle, desc))
    async_add_entities(entities)


class GeelyBinarySensor(GeelyEntity, BinarySensorEntity):
    entity_description: GeelyBinaryDescription

    def __init__(self, coordinator, vin, vehicle, description):
        super().__init__(coordinator, vin, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{vin}_{description.key}"
        self._attr_device_info = self.device_info

    @property
    def is_on(self) -> bool | None:
        raw = _dig(
            self.coordinator.data or {}, f"{self.vin}.{self.entity_description.path}"
        )
        value = _to_bool(raw)
        if value is None:
            return None
        if self.entity_description.inverted:
            return not value
        return value
