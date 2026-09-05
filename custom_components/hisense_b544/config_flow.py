"""Config flow for Hisense B544(E)."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
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
    CONF_SCAN_INTERVAL,
    CONF_TRANSPORT,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
    TRANSPORTS,
)
from .transport import params_from_data, unique_id_from_data

_NON_EMPTY_STRING = vol.All(str, str.strip, vol.Length(min=1))
_SCAN_INTERVAL = vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL))


class HisenseB544ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create a config entry for one B544 Modbus unit."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow for a configured B544."""
        return HisenseB544OptionsFlow()

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
                except HomeAssistantError, ModbusError, ValueError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema: dict = {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=(user_input or {}).get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): _SCAN_INTERVAL,
            vol.Required(CONF_UNIT_ID, default=(user_input or {}).get(CONF_UNIT_ID, 1)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
            vol.Required(
                CONF_NAME, default=(user_input or {}).get(CONF_NAME, DEFAULT_NAME)
            ): _NON_EMPTY_STRING,
            vol.Optional(
                CONF_MODEL, default=(user_input or {}).get(CONF_MODEL, DEFAULT_MODEL)
            ): str,
        }
        if transport == TRANSPORT_SERIAL:
            schema |= {
                vol.Required(
                    CONF_DEVICE, default=(user_input or {}).get(CONF_DEVICE, "/dev/ttyUSB0")
                ): _NON_EMPTY_STRING,
                vol.Required(
                    CONF_BAUDRATE, default=(user_input or {}).get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
                ): vol.In(BAUDRATES),
            }
        else:
            schema |= {
                vol.Required(
                    CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")
                ): _NON_EMPTY_STRING,
                vol.Required(
                    CONF_PORT, default=(user_input or {}).get(CONF_PORT, DEFAULT_PORT)
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            }
        return self.async_show_form(
            step_id=transport, data_schema=vol.Schema(schema), errors=errors
        )


class HisenseB544OptionsFlow(OptionsFlow):
    """Configure runtime polling behaviour."""

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Configure the polling interval."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_SCAN_INTERVAL, default=current): _SCAN_INTERVAL}
            ),
        )
