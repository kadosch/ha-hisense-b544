"""State sensors for a Hisense B544(E)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTemperature

from .entity import HisenseB544Entity


@dataclass(frozen=True)
class SensorDescription:
    key: str
    name: str
    value: Callable
    device_class: SensorDeviceClass | None = None
    native_unit_of_measurement: str | None = None


DESCRIPTIONS = (
    SensorDescription(
        "indoor_temperature",
        "Indoor temperature",
        lambda data: data.indoor_temperature,
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
    ),
    SensorDescription(
        "outlet_temperature",
        "Outlet air temperature",
        lambda data: data.outlet_temperature,
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
    ),
    SensorDescription("fault_code", "Fault code", lambda data: data.fault_code),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities(
        HisenseB544Sensor(entry.runtime_data, entry, description) for description in DESCRIPTIONS
    )


class HisenseB544Sensor(HisenseB544Entity, SensorEntity):
    def __init__(self, coordinator, entry, description: SensorDescription) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

    @property
    def native_value(self):
        return self.entity_description.value(self.coordinator.data)
