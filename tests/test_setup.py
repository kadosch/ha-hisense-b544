"""Tests for config entry setup without a physical Modbus connection."""

from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from custom_components.hisense_b544 import (
    _async_update_listener,
    async_migrate_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.hisense_b544.const import (
    CONF_BAUDRATE,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TRANSPORT,
    CONF_UNIT_ID,
    MESSAGE_SPACING,
    PLATFORMS,
    SUBENTRY_TYPE_B544,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from custom_components.hisense_b544.dependencies import (
    HisenseB544Dependencies,
    set_dependencies,
)


def migration_hass(duplicate=None):
    """Return mocked config-entry storage services for migration tests."""
    return SimpleNamespace(
        config_entries=SimpleNamespace(
            async_add_subentry=MagicMock(),
            async_entry_for_domain_unique_id=MagicMock(return_value=duplicate),
            async_update_entry=MagicMock(),
        )
    )


@pytest.mark.asyncio
async def test_migration_converts_legacy_serial_device_and_preserves_registry_ids():
    entry = SimpleNamespace(
        version=1,
        entry_id="legacy-entry",
        domain="hisense_b544",
        unique_id="serial:/dev/serial/by-id/b544:7",
        data={
            CONF_TRANSPORT: TRANSPORT_SERIAL,
            CONF_DEVICE: "/dev/serial/by-id/b544",
            CONF_BAUDRATE: 19200,
            CONF_UNIT_ID: 7,
            CONF_NAME: "Legacy unit",
            CONF_MODEL: "ADT52UX4RCL8",
            CONF_SCAN_INTERVAL: 5,
        },
        options={CONF_SCAN_INTERVAL: 30},
    )
    hass = migration_hass()

    assert await async_migrate_entry(hass, entry) is True

    migrated_subentry = hass.config_entries.async_add_subentry.call_args.args[1]
    assert migrated_subentry.subentry_id == "legacy-entry"
    assert migrated_subentry.unique_id == "7"
    assert dict(migrated_subentry.data) == {
        CONF_UNIT_ID: 7,
        CONF_NAME: "Legacy unit",
        CONF_MODEL: "ADT52UX4RCL8",
        CONF_SCAN_INTERVAL: 30,
    }
    hass.config_entries.async_update_entry.assert_called_once_with(
        entry,
        data={
            CONF_TRANSPORT: TRANSPORT_SERIAL,
            CONF_DEVICE: "/dev/serial/by-id/b544",
            CONF_BAUDRATE: 19200,
            CONF_NAME: "Legacy unit bus",
        },
        options={},
        title="Legacy unit bus",
        unique_id="serial:/dev/serial/by-id/b544",
        version=2,
    )


@pytest.mark.asyncio
async def test_migration_handles_tcp_and_retains_identity_on_bus_collision():
    duplicate = SimpleNamespace(entry_id="existing-bus")
    entry = SimpleNamespace(
        version=1,
        entry_id="legacy-tcp",
        domain="hisense_b544",
        unique_id="tcp:gateway.local:502:2",
        data={
            CONF_TRANSPORT: TRANSPORT_TCP,
            CONF_HOST: "gateway.local",
            CONF_PORT: 502,
            CONF_UNIT_ID: 2,
            CONF_NAME: "Legacy TCP unit",
        },
        options={},
    )
    hass = migration_hass(duplicate)

    assert await async_migrate_entry(hass, entry) is True

    migrated_subentry = hass.config_entries.async_add_subentry.call_args.args[1]
    assert migrated_subentry.data[CONF_MODEL] == ""
    assert migrated_subentry.data[CONF_SCAN_INTERVAL] == 5
    assert hass.config_entries.async_update_entry.call_args.kwargs["data"] == {
        CONF_TRANSPORT: TRANSPORT_TCP,
        CONF_HOST: "gateway.local",
        CONF_PORT: 502,
        CONF_NAME: "Legacy TCP unit bus",
    }
    assert (
        hass.config_entries.async_update_entry.call_args.kwargs["unique_id"]
        == "tcp:gateway.local:502:2"
    )


@pytest.mark.asyncio
async def test_migration_upgrades_early_bus_shape_and_rejects_future_version():
    hass = migration_hass()
    early_bus = SimpleNamespace(version=1, data={}, options={})
    assert await async_migrate_entry(hass, early_bus) is True
    hass.config_entries.async_update_entry.assert_called_once_with(early_bus, version=2)

    hass.config_entries.async_update_entry.reset_mock()
    current_bus = SimpleNamespace(version=2, data={}, options={})
    assert await async_migrate_entry(hass, current_bus) is True
    hass.config_entries.async_update_entry.assert_not_called()

    future_entry = SimpleNamespace(version=3, data={}, options={})
    assert await async_migrate_entry(hass, future_entry) is False


@pytest.mark.asyncio
async def test_setup_creates_one_coordinator_per_subentry_on_one_shared_bus():
    units = [SimpleNamespace(set_message_spacing=MagicMock()) for _ in range(2)]
    coordinators = [SimpleNamespace(async_refresh=AsyncMock()) for _ in range(2)]
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()))
    hass.data = {}
    provider = SimpleNamespace(get_unit=MagicMock(side_effect=units))
    set_dependencies(hass, HisenseB544Dependencies(modbus=provider))
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
    with patch(
        "custom_components.hisense_b544.HisenseB544Coordinator",
        side_effect=coordinators,
    ) as factory:
        assert await async_setup_entry(hass, entry) is True

    entry.get_subentries_of_type.assert_called_once_with(SUBENTRY_TYPE_B544)
    assert [args.args[3] for args in provider.get_unit.call_args_list] == [1, 2]
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
    hass.data = {}
    provider = SimpleNamespace(get_unit=MagicMock())
    set_dependencies(hass, HisenseB544Dependencies(modbus=provider))
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

    assert await async_setup_entry(hass, entry) is True

    provider.get_unit.assert_not_called()
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
async def test_entry_update_reloads_its_bus():
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_reload=AsyncMock()))
    entry = SimpleNamespace(entry_id="entry-id")
    await _async_update_listener(hass, entry)
    hass.config_entries.async_reload.assert_awaited_once_with("entry-id")
