"""Data coordinator for a Hisense B544(E)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusError

from .b544 import (
    DI_ENERGY_SAVING,
    DI_MUTE,
    DI_POWER,
    DI_SLEEP,
    DI_SUPER,
    IR_FAN,
    IR_MODE,
    IR_TARGET_TEMPERATURE,
    B544Device,
)
from .const import CONF_UNIT_ID, DOMAIN
from .models import B544State

_LOGGER = logging.getLogger(__name__)


class HisenseB544Coordinator(DataUpdateCoordinator[B544State]):
    """Fetch one B544 snapshot every polling interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: B544Device,
        scan_interval: int,
    ) -> None:
        """Initialize polling and command coordination for one B544."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            always_update=False,
        )
        self.device = device
        self._unit_id = entry.data[CONF_UNIT_ID]
        self._operation_lock = asyncio.Lock()

    async def _async_update_data(self) -> B544State:
        """Fetch and decode the latest complete B544 state snapshot."""
        async with self._operation_lock:
            try:
                _LOGGER.debug(
                    "Polling B544 unit %s with FC02(0, 16) and FC04(1, 15)",
                    self._unit_id,
                )
                state = await self.device.async_read_state()
            except (ModbusError, ValueError) as err:
                raise UpdateFailed(f"Unable to read Hisense B544 state: {err}") from err
            _LOGGER.debug(
                "Read B544 unit %s state: power=%s mode=%s fan=%s fault=%s",
                self._unit_id,
                state.power,
                state.mode_code,
                state.fan_code,
                state.fault_code,
            )
            return state

    async def _async_confirm_discrete_input(self, address: int, field: str) -> None:
        """Read one DI and publish its real value. Caller holds the operation lock."""
        value = await self.device.async_read_discrete_input(address)
        raw_di = list(self.data.raw_di)
        raw_di[address] = value
        self.async_set_updated_data(replace(self.data, **{field: value}, raw_di=tuple(raw_di)))

    async def _async_confirm_input_register(self, address: int, field: str) -> None:
        """Read one IR and publish its real value. Caller holds the operation lock."""
        value = await self.device.async_read_input_register(address)
        raw_ir = list(self.data.raw_ir)
        raw_ir[address - 1] = value
        self.async_set_updated_data(replace(self.data, **{field: value}, raw_ir=tuple(raw_ir)))

    @asynccontextmanager
    async def _async_command(self, operation: str) -> AsyncIterator[None]:
        """Serialize a write-confirm operation and expose failures to HA."""
        async with self._operation_lock:
            try:
                _LOGGER.debug("Starting B544 unit %s command: %s", self._unit_id, operation)
                yield
            except (ModbusError, ValueError) as err:
                self.async_set_update_error(err)
                raise HomeAssistantError(f"Unable to control Hisense B544: {err}") from err
            _LOGGER.debug("Confirmed B544 unit %s command: %s", self._unit_id, operation)

    async def async_set_power(self, value: bool) -> None:
        """Write and confirm power under one operation lock."""
        async with self._async_command("set power"):
            await self.device.async_set_power(value)
            await self._async_confirm_discrete_input(DI_POWER, "power")

    async def async_set_sleep(self, value: bool) -> None:
        """Write and confirm sleep under one operation lock."""
        async with self._async_command("set sleep"):
            await self.device.async_set_sleep(value)
            await self._async_confirm_discrete_input(DI_SLEEP, "sleep")

    async def async_set_energy_saving(self, value: bool) -> None:
        """Write and confirm energy saving under one operation lock."""
        async with self._async_command("set energy saving"):
            await self.device.async_set_energy_saving(value)
            await self._async_confirm_discrete_input(DI_ENERGY_SAVING, "energy_saving")

    async def async_set_super(self, value: bool) -> None:
        """Write and confirm super under one operation lock."""
        async with self._async_command("set super"):
            await self.device.async_set_super(value)
            await self._async_confirm_discrete_input(DI_SUPER, "super_mode")

    async def async_set_mute(self, value: bool) -> None:
        """Write and confirm mute under one operation lock."""
        async with self._async_command("set mute"):
            await self.device.async_set_mute(value)
            await self._async_confirm_discrete_input(DI_MUTE, "mute")

    async def async_set_target_temperature(self, value: float) -> None:
        """Write and confirm target temperature under one operation lock."""
        async with self._async_command("set target temperature"):
            await self.device.async_set_target_temperature(value)
            await self._async_confirm_input_register(IR_TARGET_TEMPERATURE, "target_temperature")

    async def async_set_fan(self, fan_code: int) -> None:
        """Write and confirm fan mode under one operation lock."""
        async with self._async_command("set fan"):
            await self.device.async_set_fan(fan_code)
            await self._async_confirm_input_register(IR_FAN, "fan_code")

    async def async_set_mode(self, mode_code: int) -> None:
        """Write mode, power on when needed, and confirm atomically."""
        async with self._async_command("set HVAC mode"):
            await self.device.async_set_mode(mode_code)
            if not self.data.power:
                await self.device.async_set_power(True)
                await self._async_confirm_discrete_input(DI_POWER, "power")
            await self._async_confirm_input_register(IR_MODE, "mode_code")
