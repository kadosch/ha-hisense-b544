"""Climate entity for a Hisense B544(E)."""

from __future__ import annotations

from homeassistant.components.climate import ClimateEntity, HVACMode
from homeassistant.const import UnitOfTemperature

from .entity import HisenseB544Entity

READ_MODE = {
    0: HVACMode.FAN_ONLY,
    1: HVACMode.HEAT,
    2: HVACMode.COOL,
    3: HVACMode.DRY,
    5: HVACMode.AUTO,
    6: HVACMode.AUTO,
    7: HVACMode.AUTO,
}
WRITE_MODE = {
    HVACMode.FAN_ONLY: 0,
    HVACMode.HEAT: 1,
    HVACMode.COOL: 2,
    HVACMode.DRY: 3,
    HVACMode.AUTO: 4,
}
READ_FAN = {0: "auto", 1: "high", 2: "low", 3: "medium"}
WRITE_FAN = {value: key for key, value in READ_FAN.items()}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Add the device's primary climate entity."""
    async_add_entities([HisenseB544Climate(entry.runtime_data, entry)])


class HisenseB544Climate(HisenseB544Entity, ClimateEntity):
    """Reflect B544 climate state, never predicting write results."""

    _attr_name = None
    _attr_hvac_modes = list(WRITE_MODE) + [HVACMode.OFF]
    _attr_fan_modes = list(WRITE_FAN)
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 18
    _attr_max_temp = 32
    _attr_target_temperature_step = 1

    @property
    def hvac_mode(self):
        state = self.coordinator.data
        return HVACMode.OFF if not state.power else READ_MODE.get(state.mode_code, HVACMode.AUTO)

    @property
    def current_temperature(self):
        return self.coordinator.data.indoor_temperature

    @property
    def target_temperature(self):
        return self.coordinator.data.target_temperature

    @property
    def fan_mode(self):
        return READ_FAN.get(self.coordinator.data.fan_code)

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get("temperature")
        if temperature is not None:
            await self.coordinator.device.async_set_target_temperature(temperature)
            await self.coordinator.async_confirm_input_register(2, "target_temperature")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self.coordinator.device.async_set_fan(WRITE_FAN[fan_mode])
        await self.coordinator.async_confirm_input_register(8, "fan_code")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode is HVACMode.OFF:
            await self.coordinator.device.async_set_power(False)
            await self.coordinator.async_confirm_power()
        else:
            # The documented mode is sent before switching power on. Hardware validation
            # is still required for this sequence.
            await self.coordinator.device.async_set_mode(WRITE_MODE[hvac_mode])
            if not self.coordinator.data.power:
                await self.coordinator.device.async_set_power(True)
                await self.coordinator.async_confirm_power()
            await self.coordinator.async_confirm_input_register(7, "mode_code")
