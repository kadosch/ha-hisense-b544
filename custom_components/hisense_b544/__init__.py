"""Hisense B544(E) integration."""

from __future__ import annotations

import asyncio

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
    SUBENTRY_TYPE_B544,
)
from .coordinator import HisenseB544Coordinator
from .models import HisenseB544Runtime
from .transport import params_from_data

type HisenseB544ConfigEntry = ConfigEntry[HisenseB544Runtime]


async def async_setup_entry(hass: HomeAssistant, entry: HisenseB544ConfigEntry) -> bool:
    """Set up one Modbus bus and all its B544 device subentries."""
    params = params_from_data(entry.data)
    operation_lock = asyncio.Lock()
    coordinators: dict[str, HisenseB544Coordinator] = {}

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_B544):
        unit_id = subentry.data[CONF_UNIT_ID]
        unit = async_get_unit(hass, entry, params, unit_id)
        unit.set_message_spacing(MESSAGE_SPACING)
        coordinator = HisenseB544Coordinator(
            hass,
            entry,
            B544Device(unit),
            subentry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            unit_id,
            operation_lock,
        )
        await coordinator.async_refresh()
        coordinators[subentry.subentry_id] = coordinator

    entry.runtime_data = HisenseB544Runtime(
        coordinators=coordinators,
        operation_lock=operation_lock,
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HisenseB544ConfigEntry) -> bool:
    """Unload a bus entry and release all its shared Modbus units."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: HisenseB544ConfigEntry) -> None:
    """Reload the bus when its connection or device subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)
