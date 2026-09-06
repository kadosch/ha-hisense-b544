"""Unit tests for the protocol layer."""

import pytest

from custom_components.hisense_b544.b544 import B544Device


class FakeUnit:
    def __init__(self, di=None, ir=None):
        self.di = di if di is not None else [False] * 16
        self.ir = ir if ir is not None else [0] * 15
        self.calls = []

    async def read_discrete_inputs(self, address, count):
        self.calls.append(("read_discrete_inputs", address, count))
        return self.di[address : address + count]

    async def read_input_registers(self, address, count):
        self.calls.append(("read_input_registers", address, count))
        return self.ir if count == 15 else [self.ir[address - 1]]

    async def write_coil(self, address, value):
        self.calls.append(("write_coil", address, value))

    async def write_register(self, address, value):
        self.calls.append(("write_register", address, value))

    def set_message_spacing(self, seconds):
        self.calls.append(("set_message_spacing", seconds))


@pytest.mark.asyncio
async def test_read_state_uses_only_two_grouped_reads_and_correct_offsets():
    di = [False] * 16
    for offset in (0, 3, 4, 9, 10, 11, 14, 15):
        di[offset] = True
    ir = [0] * 15
    ir[0], ir[1], ir[6], ir[7], ir[8], ir[11], ir[14] = 0xFFFF, 24, 2, 3, 1, 42, 0xFFFE
    unit = FakeUnit(di, ir)

    state = await B544Device(unit).async_read_state()

    assert unit.calls == [("read_discrete_inputs", 0, 16), ("read_input_registers", 1, 15)]
    assert state.power and state.sleep and state.electric_heater and state.energy_saving
    assert state.defrost and state.compressor and state.super_mode and state.mute
    assert (state.indoor_temperature, state.target_temperature, state.mode_code) == (-1, 24, 2)
    assert (state.fan_code, state.swing_code, state.fault_code, state.outlet_temperature) == (
        3,
        1,
        42,
        -2,
    )


@pytest.mark.asyncio
async def test_super_and_mute_use_documented_asymmetric_coils():
    unit = FakeUnit()
    device = B544Device(unit)
    await device.async_set_super(True)
    await device.async_set_mute(True)
    assert unit.calls == [("write_coil", 13, True), ("write_coil", 14, True)]


@pytest.mark.asyncio
async def test_single_register_writes_and_temperature_bounds():
    unit = FakeUnit()
    device = B544Device(unit)
    await device.async_set_target_temperature(18)
    await device.async_set_mode(4)
    await device.async_set_fan(3)
    assert unit.calls == [
        ("write_register", 0, 18),
        ("write_register", 2, 4),
        ("write_register", 3, 3),
    ]
    for value in (17, 33, 20.5):
        with pytest.raises(ValueError):
            await device.async_set_target_temperature(value)


@pytest.mark.asyncio
async def test_every_documented_single_coil_write_is_used():
    unit = FakeUnit()
    device = B544Device(unit)

    await device.async_set_power(True)
    await device.async_set_sleep(False)
    await device.async_set_energy_saving(True)
    await device.async_set_super(False)
    await device.async_set_mute(True)

    assert unit.calls == [
        ("write_coil", 0, True),
        ("write_coil", 3, False),
        ("write_coil", 9, True),
        ("write_coil", 13, False),
        ("write_coil", 14, True),
    ]


@pytest.mark.asyncio
async def test_incomplete_response_is_rejected_after_the_two_reads():
    unit = FakeUnit(di=[False] * 15)

    with pytest.raises(ValueError, match="incomplete"):
        await B544Device(unit).async_read_state()

    assert unit.calls == [("read_discrete_inputs", 0, 16), ("read_input_registers", 1, 15)]

    unit = FakeUnit(ir=[0] * 14)
    with pytest.raises(ValueError, match="incomplete"):
        await B544Device(unit).async_read_state()


@pytest.mark.asyncio
async def test_invalid_mode_and_fan_are_rejected_without_writing():
    unit = FakeUnit()
    device = B544Device(unit)

    with pytest.raises(ValueError, match="mode"):
        await device.async_set_mode(5)
    with pytest.raises(ValueError, match="fan"):
        await device.async_set_fan(4)

    assert unit.calls == []


@pytest.mark.asyncio
async def test_targeted_confirmation_reads_are_single_register_requests():
    unit = FakeUnit(di=[False, True] + [False] * 14, ir=[0, 25] + [0] * 13)
    device = B544Device(unit)

    assert await device.async_read_discrete_input(1) is True
    assert await device.async_read_input_register(2) == 25

    assert unit.calls == [("read_discrete_inputs", 1, 1), ("read_input_registers", 2, 1)]


@pytest.mark.asyncio
async def test_incomplete_targeted_confirmation_responses_are_rejected():
    class EmptyUnit(FakeUnit):
        async def read_discrete_inputs(self, address, count):
            return []

        async def read_input_registers(self, address, count):
            return []

    device = B544Device(EmptyUnit())

    with pytest.raises(ValueError, match="discrete-input"):
        await device.async_read_discrete_input(0)
    with pytest.raises(ValueError, match="input-register"):
        await device.async_read_input_register(2)
