"""Data coordinator for a Hisense B544(E)."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusError

from .b544 import B544Device
from .const import DOMAIN, SCAN_INTERVAL
from .models import B544State


class HisenseB544Coordinator(DataUpdateCoordinator[B544State]):
    """Fetch one B544 snapshot every polling interval."""

    def __init__(self, hass, device: B544Device) -> None:
        super().__init__(
            hass, logger=None, name=DOMAIN, update_interval=SCAN_INTERVAL, always_update=False
        )
        self.device = device

    async def _async_update_data(self) -> B544State:
        try:
            return await self.device.async_read_state()
        except (ModbusError, ValueError) as err:
            raise UpdateFailed(f"Unable to read Hisense B544 state: {err}") from err
