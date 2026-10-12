"""Sensors for the Geely EM integration.

All paths are relative to the per-vehicle coordinator entry:
``{status, remoteState, chargingPlan, qrvs, latestSoc, bookingCharge,
travelPlan, acSchedule, powerMode, dataUsage, trips, fences}``
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTemperature

from . import GeelyEntity
from .helpers import dig as _dig


@dataclass(frozen=True)
class GeelySensorDescription(SensorEntityDescription):
    path: str = ""
    scale: float | None = None


SENSORS: tuple[GeelySensorDescription, ...] = (
    # --- from status/latest ---
    GeelySensorDescription(
        key="battery_soc",
        name="Battery",
        path="status.additionalVehicleStatus.electricVehicleStatus.chargeLevel",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GeelySensorDescription(
        key="range_electric",
        name="Range (battery)",
        path="status.additionalVehicleStatus.electricVehicleStatus.distanceToEmptyOnBatteryOnly",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
    ),
    GeelySensorDescription(
        key="time_to_fully_charged",
        name="Time to fully charged",
        path="status.additionalVehicleStatus.electricVehicleStatus.timeToFullyCharged",
        icon="mdi:battery-clock",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="min",
    ),
    GeelySensorDescription(
        key="odometer",
        name="Odometer",
        path="status.additionalVehicleStatus.maintenanceStatus.odometer",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
    ),
    GeelySensorDescription(
        key="interior_temp",
        name="Interior temperature",
        path="status.additionalVehicleStatus.climateStatus.interiorTemp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    GeelySensorDescription(
        key="avg_speed",
        name="Average speed",
        path="status.additionalVehicleStatus.runningStatus.avgSpeed",
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="km/h",
    ),
    GeelySensorDescription(
        key="power_consumption",
        name="Power consumption (avg)",
        path="status.additionalVehicleStatus.electricVehicleStatus.averPowerConsumption",
        icon="mdi:flash",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh/100km",
    ),
    GeelySensorDescription(
        key="power_consumption_trip",
        name="Power consumption (trip)",
        path="status.additionalVehicleStatus.electricVehicleStatus.averTraPowerConsumption",
        icon="mdi:flash-outline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh/100km",
    ),
    GeelySensorDescription(
        key="tyre_pressure_front_left",
        name="Tyre pressure front left",
        path="status.additionalVehicleStatus.maintenanceStatus.tyreStatusDriver",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kPa",
    ),
    GeelySensorDescription(
        key="tyre_pressure_front_right",
        name="Tyre pressure front right",
        path="status.additionalVehicleStatus.maintenanceStatus.tyreStatusPassenger",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kPa",
    ),
    GeelySensorDescription(
        key="tyre_pressure_rear_left",
        name="Tyre pressure rear left",
        path="status.additionalVehicleStatus.maintenanceStatus.tyreStatusDriverRear",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kPa",
    ),
    GeelySensorDescription(
        key="tyre_pressure_rear_right",
        name="Tyre pressure rear right",
        path="status.additionalVehicleStatus.maintenanceStatus.tyreStatusPassengerRear",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kPa",
    ),
    GeelySensorDescription(
        key="distance_to_service",
        name="Distance to service",
        path="status.additionalVehicleStatus.maintenanceStatus.distanceToService",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
    ),
    GeelySensorDescription(
        key="days_to_service",
        name="Days to service",
        path="status.additionalVehicleStatus.maintenanceStatus.daysToService",
        icon="mdi:wrench-clock",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="d",
    ),
    GeelySensorDescription(
        key="trip_meter_1",
        name="Trip meter 1",
        path="status.additionalVehicleStatus.runningStatus.tripMeter1",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
    ),
    GeelySensorDescription(
        key="trip_meter_2",
        name="Trip meter 2",
        path="status.additionalVehicleStatus.runningStatus.tripMeter2",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
    ),
    GeelySensorDescription(
        key="12v_battery_voltage",
        name="12V battery voltage",
        path="status.additionalVehicleStatus.maintenanceStatus.mainBatteryStatus.voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
    ),
    GeelySensorDescription(
        key="status_update_time",
        name="Last status update",
        path="status.updateTime",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-check",
    ),
    # --- live charging (qrvs) ---
    GeelySensorDescription(
        key="charging_power",
        name="Charging power",
        path="qrvs.chargePower",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
    ),
    GeelySensorDescription(
        key="charging_voltage",
        name="Charging voltage",
        path="qrvs.chargeVoltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
    ),
    GeelySensorDescription(
        key="charging_current",
        name="Charging current",
        path="qrvs.chargeCurrent",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
    ),
    GeelySensorDescription(
        key="charger_state",
        name="Charger state",
        path="qrvs.chargerState",
        icon="mdi:ev-station",
    ),
    # --- latest SOC snapshot ---
    GeelySensorDescription(
        key="latest_soc",
        name="Last reported SOC",
        path="latestSoc.soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        scale=10.0,
    ),
    GeelySensorDescription(
        key="latest_soc_time",
        name="Last SOC report time",
        path="latestSoc.socTime",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
    ),
    # --- power mode ---
    GeelySensorDescription(
        key="power_mode",
        name="Power mode",
        path="powerMode.powerMode",
        icon="mdi:car-electric",
    ),
    # --- SIM data usage ---
    GeelySensorDescription(
        key="data_used",
        name="SIM data used",
        path="dataUsage.usage",
        icon="mdi:sim",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="GB",
    ),
    GeelySensorDescription(
        key="data_total",
        name="SIM data total",
        path="dataUsage.total",
        icon="mdi:sim",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="GB",
    ),
    # --- scheduled charging windows ---
    GeelySensorDescription(
        key="scheduled_charging_1_enabled",
        name="Scheduled charging 1 enabled",
        path="bookingCharge.settings.0.sts",
        icon="mdi:calendar-clock",
    ),
    GeelySensorDescription(
        key="scheduled_charging_1_start",
        name="Scheduled charging 1 start",
        path="bookingCharge.settings.0.startTime",
        icon="mdi:calendar-start",
    ),
    GeelySensorDescription(
        key="scheduled_charging_1_end",
        name="Scheduled charging 1 end",
        path="bookingCharge.settings.0.endTime",
        icon="mdi:calendar-end",
    ),
    GeelySensorDescription(
        key="scheduled_charging_2_enabled",
        name="Scheduled charging 2 enabled",
        path="bookingCharge.settings.1.sts",
        icon="mdi:calendar-clock",
    ),
    GeelySensorDescription(
        key="scheduled_charging_2_start",
        name="Scheduled charging 2 start",
        path="bookingCharge.settings.1.startTime",
        icon="mdi:calendar-start",
    ),
    GeelySensorDescription(
        key="scheduled_charging_2_end",
        name="Scheduled charging 2 end",
        path="bookingCharge.settings.1.endTime",
        icon="mdi:calendar-end",
    ),
    # --- travel plan ---
    GeelySensorDescription(
        key="travel_plan_command",
        name="Travel plan command",
        path="travelPlan.command",
        icon="mdi:map-clock",
    ),
    GeelySensorDescription(
        key="travel_plan_time",
        name="Travel plan departure",
        path="travelPlan.scheduledTime",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:map-clock-outline",
    ),
    # --- AC schedule ---
    GeelySensorDescription(
        key="ac_schedule_temp",
        name="AC scheduled temperature",
        path="acSchedule.airConditioner.temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    GeelySensorDescription(
        key="ac_schedule_duration",
        name="AC scheduled duration",
        path="acSchedule.airConditioner.duration",
        icon="mdi:air-conditioner",
        native_unit_of_measurement="min",
    ),
    # --- climate detail ---
    GeelySensorDescription(
        key="seat_heating_driver",
        name="Seat heating driver",
        path="status.additionalVehicleStatus.climateStatus.drvHeatSts",
        icon="mdi:seat-heater",
    ),
    GeelySensorDescription(
        key="seat_heating_passenger",
        name="Seat heating passenger",
        path="status.additionalVehicleStatus.climateStatus.passHeatingSts",
        icon="mdi:seat-heater",
    ),
    GeelySensorDescription(
        key="sunroof_status",
        name="Sunroof",
        path="status.additionalVehicleStatus.climateStatus.sunroofOpenStatus",
        icon="mdi:car-door",
    ),
    GeelySensorDescription(
        key="window_pos_driver",
        name="Window position driver",
        path="status.additionalVehicleStatus.climateStatus.winPosDriver",
        icon="mdi:window-closed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GeelySensorDescription(
        key="pm25_interior",
        name="Interior PM2.5",
        path="status.additionalVehicleStatus.pollutionStatus.interiorPM25",
        icon="mdi:air-filter",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="µg/m³",
    ),
    GeelySensorDescription(
        key="pm25_exterior",
        name="Exterior PM2.5",
        path="status.additionalVehicleStatus.pollutionStatus.exteriorPM25",
        icon="mdi:air-filter",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="µg/m³",
    ),
    # --- trips / fences / charging plan ---
    GeelySensorDescription(
        key="trip_count",
        name="Recorded trips",
        path="trips.total",
        icon="mdi:counter",
    ),
    GeelySensorDescription(
        key="fence_count",
        name="Geofences",
        path="fence_count",
        icon="mdi:map-marker-radius",
    ),
    GeelySensorDescription(
        key="charging_plan_command",
        name="Charging plan command",
        path="chargingPlan.command",
        icon="mdi:battery-charging",
    ),
)


def _parse_value(desc: GeelySensorDescription, raw: Any):
    if raw is None or raw == "":
        return None
    if desc.device_class == SensorDeviceClass.TIMESTAMP:
        # ms since epoch (string or int) ...
        try:
            return datetime.fromtimestamp(float(raw) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass
        # ... or "YYYY-MM-DD HH:MM:SS" (server local time, treat as UTC)
        try:
            return datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except (TypeError, ValueError):
            return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    if desc.scale:
        value = value / desc.scale
    return round(value, 2)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["geely_em"][entry.entry_id]
    entities = []
    for vin in coordinator.client.vins:
        vehicle = next((v for v in coordinator.client.vehicles if v.get("vin") == vin), {})
        for desc in SENSORS:
            entities.append(GeelySensor(coordinator, vin, vehicle, desc))
    async_add_entities(entities)


class GeelySensor(GeelyEntity, SensorEntity):
    entity_description: GeelySensorDescription

    def __init__(self, coordinator, vin, vehicle, description):
        super().__init__(coordinator, vin, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{vin}_{description.key}"
        self._attr_device_info = self.device_info

    @property
    def native_value(self):
        raw = _dig(self.coordinator.data or {}, f"{self.vin}.{self.entity_description.path}")
        if self.entity_description.key == "fence_count":
            fences = raw
            return len(fences) if isinstance(fences, list) else None
        return _parse_value(self.entity_description, raw)
