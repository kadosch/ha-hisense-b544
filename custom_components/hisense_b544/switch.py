"""Mode switches for a Hisense B544(E)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription

from .entity import HisenseB544Entity


@dataclass(frozen=True, kw_only=True)
class B544SwitchEntityDescription(SwitchEntityDescription):
    """Describe a writable B544 mode switch."""

    state: Callable
    command: Callable[[object, bool], Awaitable[None]]


DESCRIPTIONS = (
    B544SwitchEntityDescription(
        key="sleep",
        translation_key="sleep",
        icon="mdi:sleep",
        state=lambda data: data.sleep,
        command=lambda coordinator, value: coordinator.async_set_sleep(value),
    ),
    B544SwitchEntityDescription(
        key="energy_saving",
        translation_key="energy_saving",
        icon="mdi:leaf",
        state=lambda data: data.energy_saving,
        command=lambda coordinator, value: coordinator.async_set_energy_saving(value),
    ),
    B544SwitchEntityDescription(
        key="super",
        translation_key="super",
        icon="mdi:fan-speed-3",
        state=lambda data: data.super_mode,
        command=lambda coordinator, value: coordinator.async_set_super(value),
    ),
    B544SwitchEntityDescription(
        key="mute",
        translation_key="mute",
        icon="mdi:volume-mute",
        state=lambda data: data.mute,
        command=lambda coordinator, value: coordinator.async_set_mute(value),
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up B544 switches for every device subentry."""
    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        subentry = entry.subentries[subentry_id]
        async_add_entities(
            (HisenseB544Switch(coordinator, subentry, description) for description in DESCRIPTIONS),
            config_subentry_id=subentry_id,
        )


class HisenseB544Switch(HisenseB544Entity, SwitchEntity):
    """Represent a documented writable B544 mode."""

    def __init__(self, coordinator, subentry, description: B544SwitchEntityDescription) -> None:
        """Initialize a B544 switch."""
        super().__init__(coordinator, subentry)
        self.entity_description = description
        self._attr_unique_id = f"{subentry.subentry_id}_{description.key}"

    @property
    def is_on(self):
        """Return the switch state from the authoritative snapshot."""
        return self.entity_description.state(self.coordinator.data)

    async def async_turn_on(self, **kwargs) -> None:
        """Enable and authoritatively confirm the represented mode."""
        await self.entity_description.command(self.coordinator, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable and authoritatively confirm the represented mode."""
        await self.entity_description.command(self.coordinator, False)
