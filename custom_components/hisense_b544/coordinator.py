"""Data coordinator for a Hisense B544(E)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusError

from .b544 import (
    DI_ENERGY_SAVING,
    DI_MUTE,
    DI_POWER,
    DI_SLEEP,
    DI_SUPER,
    B544Device,
)
from .const import DOMAIN
from .models import B544State


class HisenseB544Coordinator(DataUpdateCoordinator[B544State]):
    """Fetch one B544 snapshot every polling interval."""

    def __init__(self, hass, device: B544Device, scan_interval: int) -> None:
        super().__init__(
            hass,
            logger=None,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            always_update=False,
        )
        self.device = device

    async def _async_update_data(self) -> B544State:
        try:
            return await self.device.async_read_state()
        except (ModbusError, ValueError) as err:
            raise UpdateFailed(f"Unable to read Hisense B544 state: {err}") from err

    async def async_confirm_discrete_input(self, address: int, field: str) -> None:
        """Read one DI after a write and publish its real value."""
        try:
            value = await self.device.async_read_discrete_input(address)
        except (ModbusError, ValueError) as err:
            raise UpdateFailed(f"Unable to confirm Hisense B544 state: {err}") from err
        raw_di = list(self.data.raw_di)
        raw_di[address] = value
        self.async_set_updated_data(replace(self.data, **{field: value}, raw_di=tuple(raw_di)))

    async def async_confirm_input_register(self, address: int, field: str) -> None:
        """Read one IR after a write and publish its real value."""
        try:
            value = await self.device.async_read_input_register(address)
        except (ModbusError, ValueError) as err:
            raise UpdateFailed(f"Unable to confirm Hisense B544 state: {err}") from err
        raw_ir = list(self.data.raw_ir)
        raw_ir[address - 1] = value
        self.async_set_updated_data(replace(self.data, **{field: value}, raw_ir=tuple(raw_ir)))

    async def async_confirm_power(self) -> None:
        """Confirm power status using DI0."""
        await self.async_confirm_discrete_input(DI_POWER, "power")

    async def async_confirm_sleep(self) -> None:
        """Confirm sleep status using DI3."""
        await self.async_confirm_discrete_input(DI_SLEEP, "sleep")

    async def async_confirm_energy_saving(self) -> None:
        """Confirm energy-saving status using DI9."""
        await self.async_confirm_discrete_input(DI_ENERGY_SAVING, "energy_saving")

    async def async_confirm_super(self) -> None:
        """Confirm super status using DI14."""
        await self.async_confirm_discrete_input(DI_SUPER, "super_mode")

    async def async_confirm_mute(self) -> None:
        """Confirm mute status using DI15."""
        await self.async_confirm_discrete_input(DI_MUTE, "mute")
