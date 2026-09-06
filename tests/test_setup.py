"""Tests for config entry setup without a physical Modbus connection."""

from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from custom_components.hisense_b544 import (
    _async_update_listener,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.hisense_b544.const import (
    CONF_BAUDRATE,
    CONF_DEVICE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    MESSAGE_SPACING,
    PLATFORMS,
    SUBENTRY_TYPE_B544,
    TRANSPORT_SERIAL,
)


@pytest.mark.asyncio
async def test_setup_creates_one_coordinator_per_subentry_on_one_shared_bus():
    units = [SimpleNamespace(set_message_spacing=MagicMock()) for _ in range(2)]
    coordinators = [SimpleNamespace(async_refresh=AsyncMock()) for _ in range(2)]
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()))
    subentries = [
        SimpleNamespace(
            subentry_id="device-a",
            data={CONF_UNIT_ID: 1, CONF_SCAN_INTERVAL: 5},
        ),
        SimpleNamespace(
            subentry_id="device-b",
            data={CONF_UNIT_ID: 2, CONF_SCAN_INTERVAL: 15},
        ),
    ]
    entry = SimpleNamespace(
        data={
            "transport": TRANSPORT_SERIAL,
            CONF_DEVICE: "/dev/serial/by-id/b544",
            CONF_BAUDRATE: 19200,
            CONF_NAME: "Upstairs bus",
        }
    )
    entry.get_subentries_of_type = MagicMock(return_value=subentries)
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    with (
        patch("custom_components.hisense_b544.async_get_unit", side_effect=units) as get_unit,
        patch(
            "custom_components.hisense_b544.HisenseB544Coordinator",
            side_effect=coordinators,
        ) as factory,
    ):
        assert await async_setup_entry(hass, entry) is True

    entry.get_subentries_of_type.assert_called_once_with(SUBENTRY_TYPE_B544)
    assert [args.args[3] for args in get_unit.call_args_list] == [1, 2]
    first_call, second_call = factory.call_args_list
    assert first_call.args[:4] == (hass, entry, ANY, 5)
    assert second_call.args[:4] == (hass, entry, ANY, 15)
    assert first_call.args[4] == 1
    assert second_call.args[4] == 2
    assert first_call.args[5] is second_call.args[5]
    for unit in units:
        unit.set_message_spacing.assert_called_once_with(MESSAGE_SPACING)
    for coordinator in coordinators:
        coordinator.async_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(entry, PLATFORMS)
    assert entry.runtime_data.coordinators == {
        "device-a": coordinators[0],
        "device-b": coordinators[1],
    }
    assert entry.runtime_data.operation_lock is first_call.args[5]
    entry.async_on_unload.assert_called_once_with(entry.add_update_listener.return_value)


@pytest.mark.asyncio
async def test_setup_accepts_an_empty_bus_before_the_first_device_is_added():
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()))
    entry = SimpleNamespace(
        data={
            "transport": TRANSPORT_SERIAL,
            CONF_DEVICE: "/dev/serial/by-id/b544",
            CONF_BAUDRATE: 19200,
        },
        get_subentries_of_type=MagicMock(return_value=[]),
        async_on_unload=MagicMock(),
        add_update_listener=MagicMock(return_value=MagicMock()),
    )

    with patch("custom_components.hisense_b544.async_get_unit") as get_unit:
        assert await async_setup_entry(hass, entry) is True

    get_unit.assert_not_called()
    assert entry.runtime_data.coordinators == {}


@pytest.mark.asyncio
async def test_unload_forwards_all_platforms():
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_unload_platforms=AsyncMock(return_value=True))
    )
    entry = SimpleNamespace()
    assert await async_unload_entry(hass, entry) is True
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(entry, PLATFORMS)


@pytest.mark.asyncio
async def test_option_update_reloads_its_entry():
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_reload=AsyncMock()))
    entry = SimpleNamespace(entry_id="entry-id")
    await _async_update_listener(hass, entry)
    hass.config_entries.async_reload.assert_awaited_once_with("entry-id")
