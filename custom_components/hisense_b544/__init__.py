"""Hisense B544(E) integration."""

from __future__ import annotations

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .b544 import B544Device
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_SCAN_INTERVAL,
    MESSAGE_SPACING,
    PLATFORMS,
)
from .coordinator import HisenseB544Coordinator
from .transport import params_from_data

type HisenseB544ConfigEntry = ConfigEntry[HisenseB544Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HisenseB544ConfigEntry) -> bool:
    """Set up one physical B544 unit."""
    unit = async_get_unit(hass, entry, params_from_data(entry.data), entry.data[CONF_UNIT_ID])
    unit.set_message_spacing(MESSAGE_SPACING)
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    coordinator = HisenseB544Coordinator(hass, entry, B544Device(unit), scan_interval)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HisenseB544ConfigEntry) -> bool:
    """Unload an entry and release its shared Modbus unit."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: HisenseB544ConfigEntry) -> None:
    """Reload the coordinator when an option changes."""
    await hass.config_entries.async_reload(entry.entry_id)
