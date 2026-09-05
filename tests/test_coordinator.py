"""Coordinator error handling tests."""

from types import SimpleNamespace

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
