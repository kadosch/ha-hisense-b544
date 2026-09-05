"""Config flow for Hisense B544(E)."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult
from modbus_connection import ModbusError

from .b544 import B544Device
from .const import (
    BAUDRATES,
    CONF_BAUDRATE,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    CONF_TRANSPORT,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
    TRANSPORTS,
)
from .transport import params_from_data, unique_id_from_data


class HisenseB544ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create a config entry for one B544 Modbus unit."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Choose the Modbus transport."""
        if user_input is not None:
            if user_input[CONF_TRANSPORT] == TRANSPORT_SERIAL:
                return await self.async_step_serial()
            return await self.async_step_tcp()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_TRANSPORT, default=TRANSPORT_SERIAL): vol.In(TRANSPORTS)}
            ),
        )

    async def async_step_serial(self, user_input: dict | None = None) -> FlowResult:
        """Configure a directly connected Modbus RTU bus."""
        return await self._async_configure(TRANSPORT_SERIAL, user_input)

    async def async_step_tcp(self, user_input: dict | None = None) -> FlowResult:
        """Configure a Modbus TCP to RTU gateway."""
        return await self._async_configure(TRANSPORT_TCP, user_input)

    async def _async_configure(self, transport: str, user_input: dict | None) -> FlowResult:
        """Probe and create an entry for the selected transport."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_TRANSPORT] = transport
            if not 1 <= user_input[CONF_UNIT_ID] <= 255:
                errors[CONF_UNIT_ID] = "invalid_unit_id"
            else:
                await self.async_set_unique_id(unique_id_from_data(user_input))
                self._abort_if_unique_id_configured()
                try:
                    async with async_get_temporary_unit(
                        self.hass, params_from_data(user_input), user_input[CONF_UNIT_ID]
                    ) as unit:
                        await B544Device(unit).async_read_state()
                except (ModbusError, ValueError):
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema: dict = {
            vol.Required(CONF_UNIT_ID, default=(user_input or {}).get(CONF_UNIT_ID, 1)): vol.Coerce(
                int
            ),
            vol.Required(CONF_NAME, default=(user_input or {}).get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Optional(
                CONF_MODEL, default=(user_input or {}).get(CONF_MODEL, DEFAULT_MODEL)
            ): str,
        }
        if transport == TRANSPORT_SERIAL:
            schema |= {
                vol.Required(
                    CONF_DEVICE, default=(user_input or {}).get(CONF_DEVICE, "/dev/ttyUSB0")
                ): str,
                vol.Required(
                    CONF_BAUDRATE, default=(user_input or {}).get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
                ): vol.In(BAUDRATES),
            }
        else:
            schema |= {
                vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
                vol.Required(
                    CONF_PORT, default=(user_input or {}).get(CONF_PORT, DEFAULT_PORT)
                ): vol.Coerce(int),
            }
        return self.async_show_form(
            step_id=transport, data_schema=vol.Schema(schema), errors=errors
        )
