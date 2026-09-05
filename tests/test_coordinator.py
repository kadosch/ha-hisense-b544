"""Coordinator error handling tests."""

import asyncio
import logging
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed
from modbus_connection import ModbusConnectionError

from custom_components.hisense_b544.coordinator import HisenseB544Coordinator
from custom_components.hisense_b544.models import B544State


def snapshot() -> B544State:
    return B544State(
        power=False,
        sleep=False,
        electric_heater=False,
        energy_saving=False,
        defrost=False,
        compressor=False,
        super_mode=False,
        mute=False,
        indoor_temperature=20,
        target_temperature=20,
        mode_code=0,
        fan_code=0,
        swing_code=0,
        fault_code=0,
        outlet_temperature=20,
        raw_di=(False,) * 16,
        raw_ir=(0,) * 15,
    )


def coordinator_with(device):
    coordinator = object.__new__(HisenseB544Coordinator)
    coordinator.device = device
    coordinator._unit_id = 1
    coordinator.data = snapshot()
    coordinator._operation_lock = asyncio.Lock()
    updates = []

    def publish(data):
        updates.append(data)
        coordinator.data = data

    coordinator.async_set_updated_data = publish
    coordinator.async_set_update_error = MagicMock()
    return coordinator, updates


def test_coordinator_initializes_with_home_assistant_runtime_contract():
    hass = SimpleNamespace()
    entry = SimpleNamespace(data={"unit_id": 2}, async_on_unload=MagicMock())
    device = SimpleNamespace()

    coordinator = HisenseB544Coordinator(hass, entry, device, 15)

    assert coordinator.hass is hass
    assert coordinator.config_entry is entry
    assert coordinator.device is device
    assert coordinator.logger.name == "custom_components.hisense_b544.coordinator"
    assert isinstance(coordinator.logger, logging.Logger)
    assert coordinator.update_interval == timedelta(seconds=15)
    assert coordinator.always_update is False
    assert coordinator._unit_id == 2
    entry.async_on_unload.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_returns_authoritative_device_snapshot():
    expected = snapshot()

    async def read_state():
        return expected

    coordinator, _ = coordinator_with(SimpleNamespace(async_read_state=read_state))
    assert await coordinator._async_update_data() is expected


@pytest.mark.asyncio
async def test_coordinator_wraps_protocol_errors_as_update_failed():
    async def read_state():
        raise ValueError("short response")

    coordinator, _ = coordinator_with(SimpleNamespace(async_read_state=read_state))
    with pytest.raises(UpdateFailed, match="short response"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_targeted_confirmation_updates_only_the_authoritative_field():
    coordinator, updates = coordinator_with(
        SimpleNamespace(
            async_read_discrete_input=AsyncMock(return_value=True),
            async_read_input_register=AsyncMock(return_value=3),
        )
    )

    await coordinator._async_confirm_discrete_input(14, "super_mode")
    await coordinator._async_confirm_input_register(8, "fan_code")

    first, second = updates
    assert first.super_mode is True
    assert first.raw_di[14] is True
    assert second.fan_code == 3
    assert second.raw_ir[7] == 3


@pytest.mark.asyncio
async def test_mode_write_and_confirm_are_one_ordered_operation():
    calls = []

    async def set_mode(value):
        calls.append(("set_mode", value))

    async def set_power(value):
        calls.append(("set_power", value))

    async def read_di(address):
        calls.append(("read_di", address))
        return True

    async def read_ir(address):
        calls.append(("read_ir", address))
        return 5

    coordinator, _ = coordinator_with(
        SimpleNamespace(
            async_set_mode=set_mode,
            async_set_power=set_power,
            async_read_discrete_input=read_di,
            async_read_input_register=read_ir,
        )
    )

    await coordinator.async_set_mode(4)

    assert calls == [("set_mode", 4), ("set_power", True), ("read_di", 0), ("read_ir", 7)]
    assert coordinator.data.power is True
    assert coordinator.data.mode_code == 5


@pytest.mark.asyncio
async def test_mode_change_does_not_write_power_when_already_on():
    device = SimpleNamespace(
        async_set_mode=AsyncMock(),
        async_set_power=AsyncMock(),
        async_read_input_register=AsyncMock(return_value=2),
    )
    coordinator, _ = coordinator_with(device)
    coordinator.data = snapshot().__class__(**{**snapshot().__dict__, "power": True})

    await coordinator.async_set_mode(2)

    device.async_set_mode.assert_awaited_once_with(2)
    device.async_set_power.assert_not_awaited()
    device.async_read_input_register.assert_awaited_once_with(7)


@pytest.mark.asyncio
async def test_each_command_uses_its_targeted_authoritative_confirmation():
    device = SimpleNamespace(
        async_set_sleep=AsyncMock(),
        async_set_energy_saving=AsyncMock(),
        async_set_super=AsyncMock(),
        async_set_mute=AsyncMock(),
        async_set_target_temperature=AsyncMock(),
        async_set_fan=AsyncMock(),
        async_read_discrete_input=AsyncMock(return_value=True),
        async_read_input_register=AsyncMock(side_effect=[25, 3]),
    )
    coordinator, _ = coordinator_with(device)

    await coordinator.async_set_sleep(True)
    await coordinator.async_set_energy_saving(True)
    await coordinator.async_set_super(True)
    await coordinator.async_set_mute(True)
    await coordinator.async_set_target_temperature(25)
    await coordinator.async_set_fan(3)

    assert device.async_read_discrete_input.await_args_list == [
        ((3,), {}),
        ((9,), {}),
        ((14,), {}),
        ((15,), {}),
    ]
    assert device.async_read_input_register.await_args_list == [
        ((2,), {}),
        ((8,), {}),
    ]
    assert coordinator.data.sleep is True
    assert coordinator.data.energy_saving is True
    assert coordinator.data.super_mode is True
    assert coordinator.data.mute is True
    assert coordinator.data.target_temperature == 25
    assert coordinator.data.fan_code == 3


@pytest.mark.asyncio
async def test_command_never_publishes_the_requested_value_optimistically():
    device = SimpleNamespace(
        async_set_sleep=AsyncMock(),
        async_read_discrete_input=AsyncMock(return_value=True),
    )
    coordinator, _ = coordinator_with(device)

    await coordinator.async_set_sleep(False)

    device.async_set_sleep.assert_awaited_once_with(False)
    assert coordinator.data.sleep is True
    assert coordinator.data.raw_di[3] is True


@pytest.mark.asyncio
async def test_failed_command_marks_coordinator_unavailable():
    error = ModbusConnectionError("offline")
    coordinator, _ = coordinator_with(SimpleNamespace(async_set_power=AsyncMock(side_effect=error)))

    with pytest.raises(HomeAssistantError, match="Unable to control"):
        await coordinator.async_set_power(True)

    coordinator.async_set_update_error.assert_called_once_with(error)


@pytest.mark.asyncio
async def test_successful_command_recovers_coordinator_after_a_command_failure():
    error = ModbusConnectionError("offline")
    device = SimpleNamespace(
        async_set_power=AsyncMock(side_effect=[error, None]),
        async_read_discrete_input=AsyncMock(return_value=True),
    )
    hass = SimpleNamespace()
    entry = SimpleNamespace(data={"unit_id": 1}, async_on_unload=MagicMock())
    coordinator = HisenseB544Coordinator(hass, entry, device, 5)
    coordinator.data = snapshot()

    with pytest.raises(HomeAssistantError):
        await coordinator.async_set_power(True)
    assert coordinator.last_update_success is False

    await coordinator.async_set_power(True)
    assert coordinator.last_update_success is True
    assert coordinator.data.power is True


@pytest.mark.asyncio
async def test_polling_waits_for_complete_write_confirmation_operation():
    write_started = asyncio.Event()
    release_write = asyncio.Event()

    async def set_power(value):
        assert value is True
        write_started.set()
        await release_write.wait()

    device = SimpleNamespace(
        async_set_power=set_power,
        async_read_discrete_input=AsyncMock(return_value=True),
        async_read_state=AsyncMock(return_value=snapshot()),
    )
    coordinator, _ = coordinator_with(device)

    command_task = asyncio.create_task(coordinator.async_set_power(True))
    await write_started.wait()
    poll_task = asyncio.create_task(coordinator._async_update_data())
    await asyncio.sleep(0)

    device.async_read_state.assert_not_awaited()
    release_write.set()
    await command_task
    await poll_task

    device.async_read_discrete_input.assert_awaited_once_with(0)
    device.async_read_state.assert_awaited_once_with()
