"""Hisense B544(E) integration."""

from __future__ import annotations

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .b544 import B544Device
from .const import CONF_UNIT_ID, MESSAGE_SPACING, PLATFORMS
from .coordinator import HisenseB544Coordinator
from .transport import params_from_data

type HisenseB544ConfigEntry = ConfigEntry[HisenseB544Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HisenseB544ConfigEntry) -> bool:
    """Set up one physical B544 unit."""
    unit = async_get_unit(hass, entry, params_from_data(entry.data), entry.data[CONF_UNIT_ID])
    unit.set_message_spacing(MESSAGE_SPACING)
    coordinator = HisenseB544Coordinator(hass, B544Device(unit))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HisenseB544ConfigEntry) -> bool:
    """Unload an entry and release its shared Modbus unit."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
