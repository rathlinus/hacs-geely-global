"""Cabin climate for the Geely EM integration (ZAF AC command)."""
from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from . import GeelyEntity
from .helpers import dig as _dig

DURATION = "15"


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["geely_em"][entry.entry_id]
    entities = []
    for vin in coordinator.client.vins:
        vehicle = next((v for v in coordinator.client.vehicles if v.get("vin") == vin), {})
        entities.append(GeelyClimate(coordinator, vin, vehicle))
    async_add_entities(entities)


class GeelyClimate(GeelyEntity, ClimateEntity):
    _attr_name = "Climate"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 15.5
    _attr_max_temp = 28.5
    _attr_target_temperature_step = 0.5
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, vin, vehicle):
        super().__init__(coordinator, vin, vehicle)
        self._attr_unique_id = f"{vin}_climate"
        self._attr_device_info = self.device_info
        self._attr_target_temperature = 22.0

    @property
    def current_temperature(self) -> float | None:
        raw = _dig(self._status, "additionalVehicleStatus.climateStatus.interiorTemp")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    @property
    def hvac_mode(self) -> HVACMode | None:
        raw = _dig(self._status, "additionalVehicleStatus.climateStatus.preClimateActive")
        if raw is None or raw == "":
            return None
        on = raw if isinstance(raw, bool) else str(raw).lower() in ("1", "true")
        return HVACMode.HEAT_COOL if on else HVACMode.OFF

    async def _start(self) -> None:
        params = [
            ("AC", "true"),
            ("AC.temp", str(self._attr_target_temperature)),
            ("AC.duration", DURATION),
        ]
        client = self.coordinator.client
        await self._send(lambda vin: client.environment(vin, params))

    async def async_set_temperature(self, **kwargs) -> None:
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = float(temp)
            self.async_write_ha_state()
        if self.hvac_mode == HVACMode.HEAT_COOL:
            await self._start()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        await self._start()

    async def async_turn_off(self) -> None:
        client = self.coordinator.client
        await self._send(lambda vin: client.environment(vin, [("AC", "false")]))
