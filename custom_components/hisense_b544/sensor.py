"""State sensors for a Hisense B544(E)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature

from .entity import HisenseB544Entity


@dataclass(frozen=True, kw_only=True)
class B544SensorEntityDescription(SensorEntityDescription):
    value_fn: Callable


DESCRIPTIONS = (
    B544SensorEntityDescription(
        key="indoor_temperature",
        translation_key="indoor_temperature",
        value_fn=lambda data: data.indoor_temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    B544SensorEntityDescription(
        key="outlet_temperature",
        translation_key="outlet_temperature",
        value_fn=lambda data: data.outlet_temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    B544SensorEntityDescription(
        key="fault_code", translation_key="fault_code", value_fn=lambda data: data.fault_code
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities(
        HisenseB544Sensor(entry.runtime_data, entry, description) for description in DESCRIPTIONS
    )


class HisenseB544Sensor(HisenseB544Entity, SensorEntity):
    def __init__(self, coordinator, entry, description: B544SensorEntityDescription) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)
