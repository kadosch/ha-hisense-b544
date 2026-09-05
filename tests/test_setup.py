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
    CONF_MODEL,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    MESSAGE_SPACING,
    PLATFORMS,
    TRANSPORT_SERIAL,
)


@pytest.mark.asyncio
async def test_setup_uses_shared_unit_and_sets_spacing():
    unit = SimpleNamespace(set_message_spacing=MagicMock())
    coordinator = SimpleNamespace(async_config_entry_first_refresh=AsyncMock())
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()))
    entry = SimpleNamespace(
        data={
            "transport": TRANSPORT_SERIAL,
            CONF_DEVICE: "/dev/serial/by-id/b544",
            CONF_BAUDRATE: 19200,
            CONF_UNIT_ID: 2,
            CONF_NAME: "ADT52 P2",
            CONF_MODEL: "ADT52UX4RCL8",
            CONF_SCAN_INTERVAL: 15,
        }
    )
    entry.options = {}
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    with (
        patch("custom_components.hisense_b544.async_get_unit", return_value=unit) as get_unit,
        patch(
            "custom_components.hisense_b544.HisenseB544Coordinator", return_value=coordinator
        ) as factory,
    ):
        assert await async_setup_entry(hass, entry) is True

    get_unit.assert_called_once()
    factory.assert_called_once_with(hass, entry, ANY, 15)
    unit.set_message_spacing.assert_called_once_with(MESSAGE_SPACING)
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(entry, PLATFORMS)
    assert entry.runtime_data is coordinator


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
