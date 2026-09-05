"""Diagnostic binary sensors for a Hisense B544(E)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription

from .entity import HisenseB544Entity


@dataclass(frozen=True, kw_only=True)
class B544BinarySensorEntityDescription(BinarySensorEntityDescription):
    value_fn: Callable


DESCRIPTIONS = (
    B544BinarySensorEntityDescription(
        key="compressor", translation_key="compressor", value_fn=lambda data: data.compressor
    ),
    B544BinarySensorEntityDescription(
        key="defrost", translation_key="defrost", value_fn=lambda data: data.defrost
    ),
    B544BinarySensorEntityDescription(
        key="electric_heater",
        translation_key="electric_heater",
        value_fn=lambda data: data.electric_heater,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities(
        HisenseB544BinarySensor(entry.runtime_data, entry, description)
        for description in DESCRIPTIONS
    )


class HisenseB544BinarySensor(HisenseB544Entity, BinarySensorEntity):
    def __init__(self, coordinator, entry, description: B544BinarySensorEntityDescription) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def is_on(self):
        return self.entity_description.value_fn(self.coordinator.data)
