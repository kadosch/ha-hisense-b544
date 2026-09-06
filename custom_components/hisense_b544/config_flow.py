"""Config and subentry flows for Hisense B544(E)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    FlowType,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
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
    DEFAULT_BUS_NAME,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SUBENTRY_TYPE_B544,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
    TRANSPORTS,
)
from .transport import bus_unique_id_from_data, params_from_data

_NON_EMPTY_STRING = vol.All(str, str.strip, vol.Length(min=1))
_SCAN_INTERVAL = vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL))


def _bus_schema(transport: str, defaults: Mapping[str, Any]) -> vol.Schema:
    """Build the shared bus schema for one transport."""
    schema: dict[vol.Marker, Any] = {
        vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_BUS_NAME)): (
            _NON_EMPTY_STRING
        )
    }
    if transport == TRANSPORT_SERIAL:
        schema |= {
            vol.Required(
                CONF_DEVICE, default=defaults.get(CONF_DEVICE, "/dev/ttyUSB0")
            ): _NON_EMPTY_STRING,
            vol.Required(
                CONF_BAUDRATE,
                default=defaults.get(CONF_BAUDRATE, DEFAULT_BAUDRATE),
            ): vol.In(BAUDRATES),
        }
    else:
        schema |= {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): (_NON_EMPTY_STRING),
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
        }
    return vol.Schema(schema)


def _device_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Build the schema for one B544 device on a configured bus."""
    return vol.Schema(
        {
            vol.Required(CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, 1)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): (
                _NON_EMPTY_STRING
            ),
            vol.Optional(CONF_MODEL, default=defaults.get(CONF_MODEL, DEFAULT_MODEL)): str,
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): _SCAN_INTERVAL,
        }
    )


async def _async_probe(hass: HomeAssistant, bus_data: Mapping[str, Any], unit_id: int) -> None:
    """Read both authoritative blocks from a temporary Modbus unit."""
    async with async_get_temporary_unit(hass, params_from_data(bus_data), unit_id) as unit:
        await B544Device(unit).async_read_state()


class HisenseB544ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create and reconfigure a shared B544 Modbus bus."""

    VERSION = 2

    @classmethod
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the B544 device flow supported below a bus entry."""
        return {SUBENTRY_TYPE_B544: HisenseB544DeviceSubentryFlow}

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Choose the transport used by the shared Modbus bus."""
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

    async def async_step_serial(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Configure a directly connected shared Modbus RTU bus."""
        return await self._async_configure_bus(TRANSPORT_SERIAL, user_input)

    async def async_step_tcp(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Configure a shared bus through a Modbus TCP to RTU gateway."""
        return await self._async_configure_bus(TRANSPORT_TCP, user_input)

    async def _async_configure_bus(
        self, transport: str, user_input: dict | None
    ) -> ConfigFlowResult:
        """Create a bus entry for the selected transport."""
        if user_input is not None:
            data = {**user_input, CONF_TRANSPORT: transport}
            await self.async_set_unique_id(bus_unique_id_from_data(data))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id=transport,
            data_schema=_bus_schema(transport, {}),
        )

    async def async_step_reconfigure(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Change connection settings for an existing shared bus."""
        entry = self._get_reconfigure_entry()
        transport = entry.data[CONF_TRANSPORT]

        if user_input is not None:
            data = {**user_input, CONF_TRANSPORT: transport}
            unique_id = bus_unique_id_from_data(data)
            duplicate = self.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, unique_id)
            if duplicate is not None and duplicate.entry_id != entry.entry_id:
                raise AbortFlow("already_configured")

            return self.async_update_and_abort(
                entry,
                unique_id=unique_id,
                title=data[CONF_NAME],
                data=data,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_bus_schema(transport, user_input or entry.data),
            description_placeholders={"transport": transport},
        )

    async def async_on_create_entry(self, result: ConfigFlowResult) -> ConfigFlowResult:
        """Continue initial onboarding with the first B544 device subentry."""
        entry = result["result"]
        subentry_flow = await self.hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_B544),
            context={"source": SOURCE_USER},
        )
        result["next_flow"] = (
            FlowType.CONFIG_SUBENTRIES_FLOW,
            subentry_flow["flow_id"],
        )
        return result


class HisenseB544DeviceSubentryFlow(ConfigSubentryFlow):
    """Add or reconfigure one B544 device on a shared Modbus bus."""

    async def async_step_user(self, user_input: dict | None = None) -> SubentryFlowResult:
        """Probe and add one B544 device."""
        return await self._async_configure_device(user_input)

    async def async_step_reconfigure(self, user_input: dict | None = None) -> SubentryFlowResult:
        """Probe and update one existing B544 device."""
        return await self._async_configure_device(
            user_input,
            current_subentry=self._get_reconfigure_subentry(),
        )

    async def _async_configure_device(
        self,
        user_input: dict | None,
        *,
        current_subentry: ConfigSubentry | None = None,
    ) -> SubentryFlowResult:
        """Validate uniqueness and connectivity before storing a device."""
        entry = self._get_entry()
        defaults = user_input or (current_subentry.data if current_subentry else {})
        errors: dict[str, str] = {}

        if user_input is not None:
            unit_id = user_input[CONF_UNIT_ID]
            if not 1 <= unit_id <= 255:
                errors[CONF_UNIT_ID] = "invalid_unit_id"
            elif any(
                subentry.unique_id == str(unit_id)
                and (
                    current_subentry is None or subentry.subentry_id != current_subentry.subentry_id
                )
                for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_B544)
            ):
                raise AbortFlow("already_configured")
            else:
                try:
                    await _async_probe(self.hass, entry.data, unit_id)
                except HomeAssistantError, ModbusError, ValueError:
                    errors["base"] = "cannot_connect"
                else:
                    if current_subentry is not None:
                        return self.async_update_and_abort(
                            entry,
                            current_subentry,
                            unique_id=str(unit_id),
                            title=user_input[CONF_NAME],
                            data=user_input,
                        )
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=user_input,
                        unique_id=str(unit_id),
                    )

        return self.async_show_form(
            step_id="reconfigure" if current_subentry else "user",
            data_schema=_device_schema(defaults),
            errors=errors,
        )
