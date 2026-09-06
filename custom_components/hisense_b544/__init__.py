"""Hisense B544(E) integration."""

from __future__ import annotations

import asyncio
from types import MappingProxyType

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant

from .b544 import B544Device
from .const import (
    CONF_BAUDRATE,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TRANSPORT,
    CONF_UNIT_ID,
    DEFAULT_SCAN_INTERVAL,
    MESSAGE_SPACING,
    PLATFORMS,
    SUBENTRY_TYPE_B544,
    TRANSPORT_SERIAL,
)
from .coordinator import HisenseB544Coordinator
from .models import HisenseB544Runtime
from .transport import bus_unique_id_from_data, params_from_data

type HisenseB544ConfigEntry = ConfigEntry[HisenseB544Runtime]


async def async_migrate_entry(hass: HomeAssistant, entry: HisenseB544ConfigEntry) -> bool:
    """Migrate legacy one-device entries to a shared bus with one subentry."""
    if entry.version > 2:
        return False

    if entry.version == 1 and CONF_UNIT_ID in entry.data:
        old_data = dict(entry.data)
        device_name = old_data[CONF_NAME]
        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            old_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        device_data = {
            CONF_UNIT_ID: old_data[CONF_UNIT_ID],
            CONF_NAME: device_name,
            CONF_MODEL: old_data.get(CONF_MODEL, ""),
            CONF_SCAN_INTERVAL: scan_interval,
        }
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(device_data),
                subentry_id=entry.entry_id,
                subentry_type=SUBENTRY_TYPE_B544,
                title=device_name,
                unique_id=str(old_data[CONF_UNIT_ID]),
            ),
        )

        shared_keys = {CONF_TRANSPORT, CONF_NAME}
        if old_data[CONF_TRANSPORT] == TRANSPORT_SERIAL:
            shared_keys.update((CONF_DEVICE, CONF_BAUDRATE))
        else:
            shared_keys.update((CONF_HOST, CONF_PORT))
        bus_data = {key: value for key, value in old_data.items() if key in shared_keys}
        bus_data[CONF_NAME] = f"{device_name} bus"
        bus_unique_id = bus_unique_id_from_data(bus_data)
        duplicate = hass.config_entries.async_entry_for_domain_unique_id(
            entry.domain, bus_unique_id
        )
        if duplicate is not None and duplicate.entry_id != entry.entry_id:
            bus_unique_id = entry.unique_id
        hass.config_entries.async_update_entry(
            entry,
            data=bus_data,
            options={},
            title=bus_data[CONF_NAME],
            unique_id=bus_unique_id,
            version=2,
        )
        return True

    if entry.version == 1:
        hass.config_entries.async_update_entry(entry, version=2)
    return True


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
