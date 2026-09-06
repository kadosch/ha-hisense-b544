"""Climate entity for a Hisense B544(E)."""

from __future__ import annotations

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
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
    """Add one primary climate entity for every B544 subentry."""
    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        subentry = entry.subentries[subentry_id]
        async_add_entities(
            [HisenseB544Climate(coordinator, subentry)],
            config_subentry_id=subentry_id,
        )


class HisenseB544Climate(HisenseB544Entity, ClimateEntity):
    """Reflect B544 climate state, never predicting write results."""

    _attr_name = None
    _attr_hvac_modes = list(WRITE_MODE) + [HVACMode.OFF]
    _attr_fan_modes = list(WRITE_FAN)
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 18
    _attr_max_temp = 32
    _attr_target_temperature_step = 1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )

    def __init__(self, coordinator, subentry) -> None:
        """Initialize the primary B544 climate entity."""
        super().__init__(coordinator, subentry)
        self._attr_unique_id = f"{subentry.subentry_id}_climate"

    @property
    def hvac_mode(self):
        """Return the current HVAC mode reported by the B544."""
        state = self.coordinator.data
        return HVACMode.OFF if not state.power else READ_MODE.get(state.mode_code)

    @property
    def current_temperature(self):
        """Return the current indoor temperature."""
        return self.coordinator.data.indoor_temperature

    @property
    def target_temperature(self):
        """Return the target temperature reported by the B544."""
        return self.coordinator.data.target_temperature

    @property
    def fan_mode(self):
        """Return the current fan mode reported by the B544."""
        return READ_FAN.get(self.coordinator.data.fan_code)

    async def async_set_temperature(self, **kwargs) -> None:
        """Set and authoritatively confirm the target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is not None:
            await self.coordinator.async_set_target_temperature(temperature)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set and authoritatively confirm the fan mode."""
        await self.coordinator.async_set_fan(WRITE_FAN[fan_mode])

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set and authoritatively confirm the HVAC mode."""
        if hvac_mode is HVACMode.OFF:
            await self.coordinator.async_set_power(False)
        else:
            # The documented mode is sent before switching power on. Hardware validation
            # is still required for this sequence.
            await self.coordinator.async_set_mode(WRITE_MODE[hvac_mode])
