"""Mode switches for a Hisense B544(E)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity

from .entity import HisenseB544Entity


@dataclass(frozen=True)
class SwitchDescription:
    key: str
    name: str
    state: Callable
    command: Callable[[object, bool], Awaitable[None]]
    confirm: Callable[[object], Awaitable[None]]


DESCRIPTIONS = (
    SwitchDescription(
        "sleep",
        "Sleep",
        lambda data: data.sleep,
        lambda device, value: device.async_set_sleep(value),
        lambda coordinator: coordinator.async_confirm_sleep(),
    ),
    SwitchDescription(
        "energy_saving",
        "Energy Saving",
        lambda data: data.energy_saving,
        lambda device, value: device.async_set_energy_saving(value),
        lambda coordinator: coordinator.async_confirm_energy_saving(),
    ),
    SwitchDescription(
        "super",
        "Super",
        lambda data: data.super_mode,
        lambda device, value: device.async_set_super(value),
        lambda coordinator: coordinator.async_confirm_super(),
    ),
    SwitchDescription(
        "mute",
        "Mute",
        lambda data: data.mute,
        lambda device, value: device.async_set_mute(value),
        lambda coordinator: coordinator.async_confirm_mute(),
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities(
        HisenseB544Switch(entry.runtime_data, entry, description) for description in DESCRIPTIONS
    )


class HisenseB544Switch(HisenseB544Entity, SwitchEntity):
    def __init__(self, coordinator, entry, description: SwitchDescription) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def is_on(self):
        return self.entity_description.state(self.coordinator.data)

    async def async_turn_on(self, **kwargs) -> None:
        await self.entity_description.command(self.coordinator.device, True)
        await self.entity_description.confirm(self.coordinator)

    async def async_turn_off(self, **kwargs) -> None:
        await self.entity_description.command(self.coordinator.device, False)
        await self.entity_description.confirm(self.coordinator)
