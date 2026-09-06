"""Stateful Modbus test doubles for Home Assistant integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from custom_components.hisense_b544.b544 import (
    COIL_ENERGY_SAVING,
    COIL_MUTE,
    COIL_POWER,
    COIL_SLEEP,
    COIL_SUPER,
    DI_ENERGY_SAVING,
    DI_MUTE,
    DI_POWER,
    DI_SLEEP,
    DI_SUPER,
    IR_FAN,
    IR_MODE,
    IR_TARGET_TEMPERATURE,
    REGISTER_FAN,
    REGISTER_MODE,
    REGISTER_TARGET_TEMPERATURE,
)


class FakeModbusUnit:
    """Emulate one B544 Modbus unit with authoritative readback state."""

    def __init__(
        self,
        *,
        discrete_inputs: list[bool] | None = None,
        input_registers: list[int] | None = None,
    ) -> None:
        """Initialize register state and an operation journal."""
        self.discrete_inputs = discrete_inputs or [False] * 16
        self.input_registers = input_registers or [0] * 15
        self.calls: list[tuple[Any, ...]] = []
        self.spacing: float | None = None
        self.read_error: Exception | None = None

    def _raise_read_error(self) -> None:
        """Raise and clear the next configured read failure."""
        if self.read_error is not None:
            error = self.read_error
            self.read_error = None
            raise error

    async def read_discrete_inputs(self, address: int, count: int) -> list[bool]:
        """Return a slice of authoritative discrete-input state."""
        self.calls.append(("read_discrete_inputs", address, count))
        self._raise_read_error()
        return self.discrete_inputs[address : address + count]

    async def read_input_registers(self, address: int, count: int) -> list[int]:
        """Return a slice of authoritative input-register state."""
        self.calls.append(("read_input_registers", address, count))
        self._raise_read_error()
        start = address - 1
        return self.input_registers[start : start + count]

    async def write_coil(self, address: int, value: bool) -> None:
        """Journal one FC05 write and apply its documented readback mapping."""
        self.calls.append(("write_coil", address, value))
        read_address = {
            COIL_POWER: DI_POWER,
            COIL_SLEEP: DI_SLEEP,
            COIL_ENERGY_SAVING: DI_ENERGY_SAVING,
            COIL_SUPER: DI_SUPER,
            COIL_MUTE: DI_MUTE,
        }[address]
        self.discrete_inputs[read_address] = value

    async def write_register(self, address: int, value: int) -> None:
        """Journal one FC06 write and apply its documented readback mapping."""
        self.calls.append(("write_register", address, value))
        read_address = {
            REGISTER_TARGET_TEMPERATURE: IR_TARGET_TEMPERATURE,
            REGISTER_MODE: IR_MODE,
            REGISTER_FAN: IR_FAN,
        }[address]
        read_value = 5 if address == REGISTER_MODE and value == 4 else value
        self.input_registers[read_address - 1] = read_value

    def set_message_spacing(self, seconds: float) -> None:
        """Record the configured per-unit message spacing."""
        self.spacing = seconds


class FakeModbusUnitProvider:
    """Inject stateful units without replacing integration-owned code."""

    def __init__(self, units: dict[int, FakeModbusUnit]) -> None:
        """Initialize units and provider call journals."""
        self.units = units
        self.persistent_calls: list[tuple[Any, ...]] = []
        self.temporary_calls: list[tuple[Any, ...]] = []

    def get_unit(self, hass, entry, params, unit_id: int) -> FakeModbusUnit:
        """Return one persistent fake unit."""
        self.persistent_calls.append((hass, entry, params, unit_id))
        return self.units[unit_id]

    @asynccontextmanager
    async def temporary_unit(self, hass, params, unit_id: int) -> AsyncIterator[FakeModbusUnit]:
        """Yield one temporary fake unit."""
        self.temporary_calls.append((hass, params, unit_id))
        yield self.units[unit_id]
