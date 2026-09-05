"""Coordinator error handling tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

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


@pytest.mark.asyncio
async def test_coordinator_returns_authoritative_device_snapshot():
    expected = snapshot()

    async def read_state():
        return expected

    coordinator = object.__new__(HisenseB544Coordinator)
    coordinator.device = SimpleNamespace(async_read_state=read_state)
    assert await coordinator._async_update_data() is expected


@pytest.mark.asyncio
async def test_coordinator_wraps_protocol_errors_as_update_failed():
    async def read_state():
        raise ValueError("short response")

    coordinator = object.__new__(HisenseB544Coordinator)
    coordinator.device = SimpleNamespace(async_read_state=read_state)
    with pytest.raises(UpdateFailed, match="short response"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_targeted_confirmation_updates_only_the_authoritative_field():
    coordinator = object.__new__(HisenseB544Coordinator)
    coordinator.data = snapshot()
    coordinator.device = SimpleNamespace(
        async_read_discrete_input=AsyncMock(return_value=True),
        async_read_input_register=AsyncMock(return_value=3),
    )
    updates = []

    def publish(data):
        updates.append(data)
        coordinator.data = data

    coordinator.async_set_updated_data = publish

    await coordinator.async_confirm_discrete_input(14, "super_mode")
    await coordinator.async_confirm_input_register(8, "fan_code")

    first, second = updates
    assert first.super_mode is True
    assert first.raw_di[14] is True
    assert second.fan_code == 3
    assert second.raw_ir[7] == 3
