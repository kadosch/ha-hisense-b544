"""Diagnostic binary sensors for a Hisense B544(E)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import HisenseB544Entity


@dataclass(frozen=True)
class BinaryDescription:
    key: str
    name: str
    value: Callable


DESCRIPTIONS = (
    BinaryDescription("compressor", "Compressor", lambda data: data.compressor),
    BinaryDescription("defrost", "Defrost", lambda data: data.defrost),
    BinaryDescription("electric_heater", "Electric Heater", lambda data: data.electric_heater),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities(
        HisenseB544BinarySensor(entry.runtime_data, entry, description)
        for description in DESCRIPTIONS
    )


class HisenseB544BinarySensor(HisenseB544Entity, BinarySensorEntity):
    def __init__(self, coordinator, entry, description: BinaryDescription) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def is_on(self):
        return self.entity_description.value(self.coordinator.data)
