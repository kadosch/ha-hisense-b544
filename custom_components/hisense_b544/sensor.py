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
    """Describe a B544 numeric sensor."""

    value_fn: Callable


DESCRIPTIONS = (
    B544SensorEntityDescription(
        key="indoor_temperature",
        translation_key="indoor_temperature",
        icon="mdi:home-thermometer",
        value_fn=lambda data: data.indoor_temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    B544SensorEntityDescription(
        key="outlet_temperature",
        translation_key="outlet_temperature",
        icon="mdi:thermometer-lines",
        value_fn=lambda data: data.outlet_temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    B544SensorEntityDescription(
        key="fault_code",
        translation_key="fault_code",
        icon="mdi:alert-circle-outline",
        value_fn=lambda data: data.fault_code,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up B544 sensors for every device subentry."""
    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        subentry = entry.subentries[subentry_id]
        async_add_entities(
            (HisenseB544Sensor(coordinator, subentry, description) for description in DESCRIPTIONS),
            config_subentry_id=subentry_id,
        )


class HisenseB544Sensor(HisenseB544Entity, SensorEntity):
    """Represent a documented B544 numeric value."""

    def __init__(self, coordinator, subentry, description: B544SensorEntityDescription) -> None:
        """Initialize a B544 sensor."""
        super().__init__(coordinator, subentry)
        self.entity_description = description
        self._attr_unique_id = f"{subentry.subentry_id}_{description.key}"

    @property
    def native_value(self):
        """Return the value from the authoritative coordinator snapshot."""
        return self.entity_description.value_fn(self.coordinator.data)
