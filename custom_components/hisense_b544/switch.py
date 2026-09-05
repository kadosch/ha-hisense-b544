"""Mode switches for a Hisense B544(E)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription

from .entity import HisenseB544Entity


@dataclass(frozen=True, kw_only=True)
class B544SwitchEntityDescription(SwitchEntityDescription):
    state: Callable
    command: Callable[[object, bool], Awaitable[None]]


DESCRIPTIONS = (
    B544SwitchEntityDescription(
        key="sleep",
        translation_key="sleep",
        state=lambda data: data.sleep,
        command=lambda coordinator, value: coordinator.async_set_sleep(value),
    ),
    B544SwitchEntityDescription(
        key="energy_saving",
        translation_key="energy_saving",
        state=lambda data: data.energy_saving,
        command=lambda coordinator, value: coordinator.async_set_energy_saving(value),
    ),
    B544SwitchEntityDescription(
        key="super",
        translation_key="super",
        state=lambda data: data.super_mode,
        command=lambda coordinator, value: coordinator.async_set_super(value),
    ),
    B544SwitchEntityDescription(
        key="mute",
        translation_key="mute",
        state=lambda data: data.mute,
        command=lambda coordinator, value: coordinator.async_set_mute(value),
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities(
        HisenseB544Switch(entry.runtime_data, entry, description) for description in DESCRIPTIONS
    )


class HisenseB544Switch(HisenseB544Entity, SwitchEntity):
    def __init__(self, coordinator, entry, description: B544SwitchEntityDescription) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def is_on(self):
        return self.entity_description.state(self.coordinator.data)

    async def async_turn_on(self, **kwargs) -> None:
        await self.entity_description.command(self.coordinator, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.entity_description.command(self.coordinator, False)
