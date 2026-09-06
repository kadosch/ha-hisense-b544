"""Config and subentry flows for Hisense B544(E)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
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
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
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
from .dependencies import get_dependencies
from .transport import bus_unique_id_from_data, params_from_data

_TEXT_SELECTOR = TextSelector()


def _integer(value: Any) -> int | None:
    """Return an integer without silently truncating fractional values."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    try:
        integer = int(value)
    except TypeError, ValueError:
        return None
    return integer if integer == value else None


def _normalized_text(value: Any) -> str | None:
    """Return stripped non-empty text, or None for invalid input."""
    if not isinstance(value, str) or not (value := value.strip()):
        return None
    return value


def _normalize_bus_input(
    transport: str, user_input: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Normalize and semantically validate shared-bus form input."""
    data = dict(user_input)
    errors: dict[str, str] = {}

    if (name := _normalized_text(data.get(CONF_NAME))) is None:
        errors[CONF_NAME] = "invalid_name"
    else:
        data[CONF_NAME] = name

    if transport == TRANSPORT_SERIAL:
        if (device := _normalized_text(data.get(CONF_DEVICE))) is None:
            errors[CONF_DEVICE] = "invalid_device"
        else:
            data[CONF_DEVICE] = device
        baudrate = _integer(data.get(CONF_BAUDRATE))
        if baudrate not in BAUDRATES:
            errors[CONF_BAUDRATE] = "invalid_baudrate"
        else:
            data[CONF_BAUDRATE] = baudrate
    else:
        if (host := _normalized_text(data.get(CONF_HOST))) is None:
            errors[CONF_HOST] = "invalid_host"
        else:
            data[CONF_HOST] = host
        port = _integer(data.get(CONF_PORT))
        if port is None or not 1 <= port <= 65535:
            errors[CONF_PORT] = "invalid_port"
        else:
            data[CONF_PORT] = port

    data[CONF_TRANSPORT] = transport
    return data, errors


def _normalize_device_input(
    user_input: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Normalize and semantically validate B544 device form input."""
    data = dict(user_input)
    errors: dict[str, str] = {}

    unit_id = _integer(data.get(CONF_UNIT_ID))
    if unit_id is None or not 1 <= unit_id <= 255:
        errors[CONF_UNIT_ID] = "invalid_unit_id"
    else:
        data[CONF_UNIT_ID] = unit_id

    if (name := _normalized_text(data.get(CONF_NAME))) is None:
        errors[CONF_NAME] = "invalid_name"
    else:
        data[CONF_NAME] = name

    model = data.get(CONF_MODEL, DEFAULT_MODEL)
    data[CONF_MODEL] = model.strip() if isinstance(model, str) and model.strip() else DEFAULT_MODEL

    scan_interval = _integer(data.get(CONF_SCAN_INTERVAL))
    if scan_interval is None or not MIN_SCAN_INTERVAL <= scan_interval <= MAX_SCAN_INTERVAL:
        errors[CONF_SCAN_INTERVAL] = "invalid_scan_interval"
    else:
        data[CONF_SCAN_INTERVAL] = scan_interval

    return data, errors


def _bus_schema(transport: str, defaults: Mapping[str, Any]) -> vol.Schema:
    """Build the shared bus schema for one transport."""
    schema: dict[vol.Marker, Any] = {
        vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_BUS_NAME)): _TEXT_SELECTOR
    }
    if transport == TRANSPORT_SERIAL:
        schema |= {
            vol.Required(
                CONF_DEVICE, default=defaults.get(CONF_DEVICE, "/dev/ttyUSB0")
            ): _TEXT_SELECTOR,
            vol.Required(
                CONF_BAUDRATE,
                default=str(defaults.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[str(baudrate) for baudrate in BAUDRATES],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    else:
        schema |= {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): _TEXT_SELECTOR,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=65535,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    return vol.Schema(schema)


def _device_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Build the schema for one B544 device on a configured bus."""
    return vol.Schema(
        {
            vol.Required(CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, 1)): NumberSelector(
                NumberSelectorConfig(min=1, max=255, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): _TEXT_SELECTOR,
            vol.Optional(
                CONF_MODEL, default=defaults.get(CONF_MODEL, DEFAULT_MODEL)
            ): _TEXT_SELECTOR,
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


async def _async_probe(hass: HomeAssistant, bus_data: Mapping[str, Any], unit_id: int) -> None:
    """Read both authoritative blocks from a temporary Modbus unit."""
    async with get_dependencies(hass).modbus.temporary_unit(
        hass, params_from_data(bus_data), unit_id
    ) as unit:
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
                {
                    vol.Required(CONF_TRANSPORT, default=TRANSPORT_SERIAL): SelectSelector(
                        SelectSelectorConfig(
                            options=list(TRANSPORTS),
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key=CONF_TRANSPORT,
                        )
                    )
                }
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
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _normalize_bus_input(transport, user_input)
            if not errors:
                await self.async_set_unique_id(bus_unique_id_from_data(data))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id=transport,
            data_schema=_bus_schema(transport, user_input or {}),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Change connection settings for an existing shared bus."""
        entry = self._get_reconfigure_entry()
        transport = entry.data[CONF_TRANSPORT]
        errors: dict[str, str] = {}

        if user_input is not None:
            data, errors = _normalize_bus_input(transport, user_input)
            if not errors:
                unique_id = bus_unique_id_from_data(data)
                duplicate = self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN, unique_id
                )
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
            errors=errors,
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
            data, errors = _normalize_device_input(user_input)
            unit_id = data.get(CONF_UNIT_ID)
            if not errors and any(
                subentry.unique_id == str(unit_id)
                and (
                    current_subentry is None or subentry.subentry_id != current_subentry.subentry_id
                )
                for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_B544)
            ):
                raise AbortFlow("already_configured")
            if not errors:
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
                            title=data[CONF_NAME],
                            data=data,
                        )
                    return self.async_create_entry(
                        title=data[CONF_NAME],
                        data=data,
                        unique_id=str(unit_id),
                    )

        return self.async_show_form(
            step_id="reconfigure" if current_subentry else "user",
            data_schema=_device_schema(defaults),
            errors=errors,
        )
