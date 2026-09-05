"""Hisense B544(E) Modbus protocol.

This module deliberately knows no Home Assistant entity classes.  One state
refresh is exactly FC02(0, 16) followed by FC04(1, 15).
"""

from __future__ import annotations

from typing import Protocol

from modbus_connection.decode import decode_int16

from .const import MAX_TEMPERATURE, MIN_TEMPERATURE
from .models import B544State


class B544Unit(Protocol):
    """Subset of ModbusUnit used by this device."""

    async def read_discrete_inputs(self, address: int, count: int) -> list[bool]: ...
    async def read_input_registers(self, address: int, count: int) -> list[int]: ...
    async def write_coil(self, address: int, value: bool) -> None: ...
    async def write_register(self, address: int, value: int) -> None: ...
    def set_message_spacing(self, seconds: float) -> None: ...


# FC02 offsets
DI_POWER = 0
DI_SLEEP = 3
DI_ELECTRIC_HEATER = 4
DI_ENERGY_SAVING = 9
DI_DEFROST = 10
DI_COMPRESSOR = 11
DI_SUPER = 14
DI_MUTE = 15

# FC04 addresses
IR_INDOOR_TEMPERATURE = 1
IR_TARGET_TEMPERATURE = 2
IR_MODE = 7
IR_FAN = 8
IR_SWING = 9
IR_FAULT = 12
IR_OUTLET_TEMPERATURE = 15

# FC05 addresses. Super and mute intentionally differ from their read offsets.
COIL_POWER = 0
COIL_SLEEP = 3
COIL_ENERGY_SAVING = 9
COIL_SUPER = 13
COIL_MUTE = 14

# FC06 addresses
REGISTER_TARGET_TEMPERATURE = 0
REGISTER_MODE = 2
REGISTER_FAN = 3


class B544Device:
    """Minimal B544(E) device client backed by HA's shared ModbusUnit."""

    def __init__(self, unit: B544Unit) -> None:
        self._unit = unit

    async def async_read_state(self) -> B544State:
        """Read the two documented contiguous B544 state blocks."""
        discrete_inputs = await self._unit.read_discrete_inputs(0, 16)
        input_registers = await self._unit.read_input_registers(1, 15)
        if len(discrete_inputs) != 16 or len(input_registers) != 15:
            raise ValueError("B544 returned an incomplete state block")

        di = tuple(discrete_inputs)
        ir = tuple(input_registers)
        return B544State(
            power=di[DI_POWER],
            sleep=di[DI_SLEEP],
            electric_heater=di[DI_ELECTRIC_HEATER],
            energy_saving=di[DI_ENERGY_SAVING],
            defrost=di[DI_DEFROST],
            compressor=di[DI_COMPRESSOR],
            super_mode=di[DI_SUPER],
            mute=di[DI_MUTE],
            indoor_temperature=decode_int16([ir[IR_INDOOR_TEMPERATURE - 1]]),
            target_temperature=ir[IR_TARGET_TEMPERATURE - 1],
            mode_code=ir[IR_MODE - 1],
            fan_code=ir[IR_FAN - 1],
            swing_code=ir[IR_SWING - 1],
            fault_code=ir[IR_FAULT - 1],
            outlet_temperature=decode_int16([ir[IR_OUTLET_TEMPERATURE - 1]]),
            raw_di=di,
            raw_ir=ir,
        )

    async def async_set_power(self, value: bool) -> None:
        await self._unit.write_coil(COIL_POWER, value)

    async def async_set_sleep(self, value: bool) -> None:
        await self._unit.write_coil(COIL_SLEEP, value)

    async def async_set_energy_saving(self, value: bool) -> None:
        await self._unit.write_coil(COIL_ENERGY_SAVING, value)

    async def async_set_super(self, value: bool) -> None:
        await self._unit.write_coil(COIL_SUPER, value)

    async def async_set_mute(self, value: bool) -> None:
        await self._unit.write_coil(COIL_MUTE, value)

    async def async_read_discrete_input(self, address: int) -> bool:
        """Read one authoritative discrete-input status value."""
        values = await self._unit.read_discrete_inputs(address, 1)
        if len(values) != 1:
            raise ValueError("B544 returned an incomplete discrete-input response")
        return values[0]

    async def async_read_input_register(self, address: int) -> int:
        """Read one authoritative input-register status value."""
        values = await self._unit.read_input_registers(address, 1)
        if len(values) != 1:
            raise ValueError("B544 returned an incomplete input-register response")
        return values[0]

    async def async_set_target_temperature(self, value: float) -> None:
        if value != int(value) or not MIN_TEMPERATURE <= value <= MAX_TEMPERATURE:
            raise ValueError(
                f"Target temperature must be an integer from {MIN_TEMPERATURE} to {MAX_TEMPERATURE}"
            )
        await self._unit.write_register(REGISTER_TARGET_TEMPERATURE, int(value))

    async def async_set_mode(self, value: int) -> None:
        if value not in (0, 1, 2, 3, 4):
            raise ValueError("Invalid B544 write mode")
        await self._unit.write_register(REGISTER_MODE, value)

    async def async_set_fan(self, value: int) -> None:
        if value not in (0, 1, 2, 3):
            raise ValueError("Invalid B544 fan mode")
        await self._unit.write_register(REGISTER_FAN, value)
