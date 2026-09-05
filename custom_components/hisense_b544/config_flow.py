"""Config flow for Hisense B544(E)."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult
from modbus_connection import ModbusError, ModbusSerialParams

from .b544 import B544Device
from .const import (
    BAUDRATES,
    CONF_BAUDRATE,
    CONF_DEVICE,
    CONF_MODEL,
    CONF_NAME,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DOMAIN,
)


class HisenseB544ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create a config entry for one B544 Modbus unit."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not 1 <= user_input[CONF_UNIT_ID] <= 255:
                errors[CONF_UNIT_ID] = "invalid_unit_id"
            else:
                unique_id = f"serial:{user_input[CONF_DEVICE]}:{user_input[CONF_UNIT_ID]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                try:
                    params = ModbusSerialParams(
                        device=user_input[CONF_DEVICE],
                        baudrate=user_input[CONF_BAUDRATE],
                        bytesize=8,
                        parity="N",
                        stopbits=1,
                        framer="rtu",
                    )
                    async with async_get_temporary_unit(
                        self.hass, params, user_input[CONF_UNIT_ID]
                    ) as unit:
                        await B544Device(unit).async_read_state()
                except (ModbusError, ValueError):
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEVICE, default=(user_input or {}).get(CONF_DEVICE, "/dev/ttyUSB0")
                ): str,
                vol.Required(
                    CONF_BAUDRATE, default=(user_input or {}).get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
                ): vol.In(BAUDRATES),
                vol.Required(
                    CONF_UNIT_ID, default=(user_input or {}).get(CONF_UNIT_ID, 1)
                ): vol.Coerce(int),
                vol.Required(
                    CONF_NAME, default=(user_input or {}).get(CONF_NAME, DEFAULT_NAME)
                ): str,
                vol.Optional(
                    CONF_MODEL, default=(user_input or {}).get(CONF_MODEL, DEFAULT_MODEL)
                ): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
