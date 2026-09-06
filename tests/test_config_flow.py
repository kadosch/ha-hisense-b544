"""Config-flow and B544 subentry-flow tests."""

from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER, FlowType
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError

from custom_components.hisense_b544.config_flow import (
    HisenseB544ConfigFlow,
    HisenseB544DeviceSubentryFlow,
)
from custom_components.hisense_b544.const import (
    CONF_BAUDRATE,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TRANSPORT,
    CONF_UNIT_ID,
    DEFAULT_BUS_NAME,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SUBENTRY_TYPE_B544,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from custom_components.hisense_b544.dependencies import (
    HisenseB544Dependencies,
    set_dependencies,
)


class TemporaryUnit:
    """Async context manager returned by HA's temporary-unit API."""

    async def __aenter__(self):
        """Return the temporary unit."""
        return self

    async def __aexit__(self, *args):
        """Release the temporary unit."""
        return False


def serial_bus_input(**changes):
    """Return valid serial bus form data."""
    data = {
        CONF_DEVICE: "/dev/serial/by-id/b544",
        CONF_BAUDRATE: 19200,
        CONF_NAME: "Main HVAC bus",
    }
    data.update(changes)
    return data


def tcp_bus_input(**changes):
    """Return valid TCP gateway bus form data."""
    data = {CONF_HOST: "Gateway.LOCAL", CONF_PORT: 1502, CONF_NAME: "Gateway bus"}
    data.update(changes)
    return data


def device_input(**changes):
    """Return valid B544 device form data."""
    data = {
        CONF_UNIT_ID: 1,
        CONF_NAME: "Unit A",
        CONF_MODEL: "ADT52UX4RCL8",
        CONF_SCAN_INTERVAL: 5,
    }
    data.update(changes)
    return data


def make_subentry(subentry_id="device-a", unit_id=1, **changes):
    """Return a minimal immutable B544 config subentry."""
    data = device_input(**{CONF_UNIT_ID: unit_id}, **changes)
    return SimpleNamespace(
        subentry_id=subentry_id,
        unique_id=str(unit_id),
        data=MappingProxyType(data),
    )


def make_bus_entry(*subentries, transport=TRANSPORT_SERIAL):
    """Return a minimal bus config entry containing device subentries."""
    if transport == TRANSPORT_SERIAL:
        data = {**serial_bus_input(), CONF_TRANSPORT: transport}
    else:
        data = {**tcp_bus_input(), CONF_TRANSPORT: transport}
    by_id = {subentry.subentry_id: subentry for subentry in subentries}
    return SimpleNamespace(
        entry_id="bus-entry",
        data=MappingProxyType(data),
        subentries=MappingProxyType(by_id),
        get_subentries_of_type=MagicMock(return_value=list(subentries)),
    )


def config_flow(entry_for_unique_id=None):
    """Return a parent config flow with Home Assistant helpers mocked."""
    current = HisenseB544ConfigFlow()
    current.hass = SimpleNamespace(
        data={},
        config_entries=SimpleNamespace(
            async_entry_for_domain_unique_id=MagicMock(return_value=entry_for_unique_id)
        ),
    )
    current.async_set_unique_id = AsyncMock()
    current._abort_if_unique_id_configured = MagicMock()
    current.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    current.async_show_form = MagicMock(return_value={"type": "form"})
    return current


def subentry_flow(entry, *, source=SOURCE_USER, subentry_id=None):
    """Return a B544 subentry flow attached to a parent entry."""
    current = HisenseB544DeviceSubentryFlow()
    current.hass = SimpleNamespace(
        data={}, config_entries=SimpleNamespace(async_get_known_entry=MagicMock(return_value=entry))
    )
    current.handler = (entry.entry_id, SUBENTRY_TYPE_B544)
    current.context = {"source": source}
    if subentry_id is not None:
        current.context["subentry_id"] = subentry_id
    current.async_show_form = MagicMock(return_value={"type": "form"})
    current.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    current.async_update_and_abort = MagicMock(return_value={"type": "abort"})
    return current


@pytest.mark.asyncio
async def test_transport_form_routes_to_selected_bus_form():
    """The first step must route to serial or TCP bus configuration."""
    current = config_flow()
    assert await current.async_step_user() == {"type": "form"}
    assert current.async_show_form.call_args.kwargs["step_id"] == "user"

    current.async_step_serial = AsyncMock(return_value={"type": "serial"})
    current.async_step_tcp = AsyncMock(return_value={"type": "tcp"})
    assert await current.async_step_user({CONF_TRANSPORT: TRANSPORT_SERIAL}) == {"type": "serial"}
    assert await current.async_step_user({CONF_TRANSPORT: TRANSPORT_TCP}) == {"type": "tcp"}


@pytest.mark.asyncio
async def test_serial_bus_creation_uses_endpoint_identity_and_no_probe():
    """A serial parent entry stores only shared connection settings."""
    current = config_flow()
    data = serial_bus_input()

    with patch("custom_components.hisense_b544.config_flow._async_probe") as probe:
        assert await current.async_step_serial(data) == {"type": "create_entry"}

    current.async_set_unique_id.assert_awaited_once_with("serial:/dev/serial/by-id/b544")
    current._abort_if_unique_id_configured.assert_called_once_with()
    current.async_create_entry.assert_called_once_with(
        title="Main HVAC bus",
        data={**data, CONF_TRANSPORT: TRANSPORT_SERIAL},
    )
    probe.assert_not_called()


@pytest.mark.asyncio
async def test_tcp_bus_creation_normalizes_gateway_identity():
    """A TCP bus identity follows modbus-connection host normalization."""
    current = config_flow()
    data = tcp_bus_input()

    assert await current.async_step_tcp(data) == {"type": "create_entry"}

    current.async_set_unique_id.assert_awaited_once_with("tcp:gateway.local:1502")
    current.async_create_entry.assert_called_once_with(
        title="Gateway bus",
        data={**data, CONF_TRANSPORT: TRANSPORT_TCP},
    )


@pytest.mark.asyncio
async def test_duplicate_bus_is_aborted():
    """A second parent entry cannot claim the same physical endpoint."""
    current = config_flow()
    current._abort_if_unique_id_configured.side_effect = AbortFlow("already_configured")

    with pytest.raises(AbortFlow):
        await current.async_step_serial(serial_bus_input())

    current.async_create_entry.assert_not_called()


@pytest.mark.asyncio
async def test_bus_forms_validate_transport_specific_fields():
    """Bus forms reject blank endpoints and unsupported link settings."""
    current = config_flow()
    await current.async_step_serial()
    serial_schema = current.async_show_form.call_args.kwargs["data_schema"]
    assert serial_schema({})[CONF_NAME] == DEFAULT_BUS_NAME
    for field, value in (
        (CONF_DEVICE, " "),
        (CONF_NAME, ""),
        (CONF_BAUDRATE, 115200),
    ):
        with pytest.raises(vol.Invalid):
            serial_schema(serial_bus_input(**{field: value}))

    await current.async_step_tcp()
    tcp_schema = current.async_show_form.call_args.kwargs["data_schema"]
    assert tcp_schema(tcp_bus_input())[CONF_HOST] == "Gateway.LOCAL"
    for field, value in ((CONF_HOST, " "), (CONF_PORT, 0), (CONF_PORT, 65536)):
        with pytest.raises(vol.Invalid):
            tcp_schema(tcp_bus_input(**{field: value}))


def test_config_flow_exposes_b544_device_subentries():
    """The bus entry must advertise the B544 subentry flow to Home Assistant."""
    supported = HisenseB544ConfigFlow.async_get_supported_subentry_types(make_bus_entry())
    assert supported == {SUBENTRY_TYPE_B544: HisenseB544DeviceSubentryFlow}


@pytest.mark.asyncio
async def test_new_bus_continues_directly_to_first_device_flow():
    """Initial setup should guide the user into adding the first B544."""
    current = config_flow()
    entry = SimpleNamespace(entry_id="bus-entry")
    current.hass.config_entries.subentries = SimpleNamespace(
        async_init=AsyncMock(return_value={"flow_id": "device-flow"})
    )
    result = {"type": "create_entry", "result": entry}

    assert await current.async_on_create_entry(result) == {
        **result,
        "next_flow": (FlowType.CONFIG_SUBENTRIES_FLOW, "device-flow"),
    }
    current.hass.config_entries.subentries.async_init.assert_awaited_once_with(
        ("bus-entry", SUBENTRY_TYPE_B544),
        context={"source": SOURCE_USER},
    )


@pytest.mark.asyncio
async def test_device_form_validates_all_device_specific_fields():
    """Device subentries own Unit ID, metadata, and polling interval."""
    current = subentry_flow(make_bus_entry())
    assert await current.async_step_user() == {"type": "form"}
    schema = current.async_show_form.call_args.kwargs["data_schema"]
    assert schema(device_input())[CONF_SCAN_INTERVAL] == MIN_SCAN_INTERVAL
    for field, value in (
        (CONF_UNIT_ID, 0),
        (CONF_UNIT_ID, 256),
        (CONF_NAME, " "),
        (CONF_SCAN_INTERVAL, MIN_SCAN_INTERVAL - 1),
        (CONF_SCAN_INTERVAL, MAX_SCAN_INTERVAL + 1),
    ):
        with pytest.raises(vol.Invalid):
            schema(device_input(**{field: value}))


@pytest.mark.asyncio
async def test_valid_device_probe_reads_state_and_creates_unique_subentry():
    """Adding a B544 probes its Unit ID over the parent bus."""
    entry = make_bus_entry()
    current = subentry_flow(entry)
    temporary = TemporaryUnit()
    provider = SimpleNamespace(temporary_unit=MagicMock(return_value=temporary))
    set_dependencies(current.hass, HisenseB544Dependencies(modbus=provider))

    with patch(
        "custom_components.hisense_b544.config_flow.B544Device.async_read_state",
        new=AsyncMock(),
    ) as read_state:
        assert await current.async_step_user(device_input()) == {"type": "create_entry"}

    provider.temporary_unit.assert_called_once()
    assert provider.temporary_unit.call_args.args[2] == 1
    read_state.assert_awaited_once_with()
    current.async_create_entry.assert_called_once_with(
        title="Unit A", data=device_input(), unique_id="1"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ValueError("offline"), HomeAssistantError("conflict")])
async def test_device_probe_failure_returns_cannot_connect(error):
    """Protocol and connection failures keep the device form open."""
    current = subentry_flow(make_bus_entry())
    with patch("custom_components.hisense_b544.config_flow._async_probe", side_effect=error):
        assert await current.async_step_user(device_input()) == {"type": "form"}
    assert current.async_show_form.call_args.kwargs["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_duplicate_unit_id_is_aborted_before_probe():
    """Unit IDs must be unique within their parent bus."""
    current = subentry_flow(make_bus_entry(make_subentry()))
    with (
        patch("custom_components.hisense_b544.config_flow._async_probe") as probe,
        pytest.raises(AbortFlow),
    ):
        await current.async_step_user(device_input())
    probe.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_unit_id_is_rejected_before_probe_when_called_directly():
    """The flow remains defensive when invoked without schema validation."""
    current = subentry_flow(make_bus_entry())
    with patch("custom_components.hisense_b544.config_flow._async_probe") as probe:
        assert await current.async_step_user(device_input(**{CONF_UNIT_ID: 0})) == {"type": "form"}
    assert current.async_show_form.call_args.kwargs["errors"] == {CONF_UNIT_ID: "invalid_unit_id"}
    probe.assert_not_called()


@pytest.mark.asyncio
async def test_device_reconfigure_uses_current_defaults_and_updates_subentry():
    """Reconfiguration can change Unit ID, metadata, and polling interval."""
    existing = make_subentry()
    entry = make_bus_entry(existing)
    current = subentry_flow(
        entry,
        source=SOURCE_RECONFIGURE,
        subentry_id=existing.subentry_id,
    )

    assert await current.async_step_reconfigure() == {"type": "form"}
    schema = current.async_show_form.call_args.kwargs["data_schema"]
    assert schema({})[CONF_NAME] == "Unit A"

    updated = device_input(**{CONF_UNIT_ID: 2, CONF_NAME: "Unit B", CONF_SCAN_INTERVAL: 30})
    with patch("custom_components.hisense_b544.config_flow._async_probe", new=AsyncMock()):
        assert await current.async_step_reconfigure(updated) == {"type": "abort"}

    current.async_update_and_abort.assert_called_once_with(
        entry,
        existing,
        unique_id="2",
        title="Unit B",
        data=updated,
    )


@pytest.mark.asyncio
async def test_device_reconfigure_allows_keeping_its_own_unit_id():
    """A device does not collide with itself during reconfiguration."""
    existing = make_subentry()
    entry = make_bus_entry(existing)
    current = subentry_flow(
        entry,
        source=SOURCE_RECONFIGURE,
        subentry_id=existing.subentry_id,
    )
    with patch("custom_components.hisense_b544.config_flow._async_probe", new=AsyncMock()):
        assert await current.async_step_reconfigure(device_input()) == {"type": "abort"}


@pytest.mark.asyncio
async def test_bus_reconfigure_updates_connection_without_conflicting_probe():
    """Changing a bus saves settings for the subsequent connection reload."""
    entry = make_bus_entry(make_subentry(unit_id=7))
    current = config_flow()
    current.context = {"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    current._get_reconfigure_entry = MagicMock(return_value=entry)
    current.async_update_and_abort = MagicMock(return_value={"type": "abort"})
    updated = serial_bus_input(**{CONF_BAUDRATE: 38400, CONF_NAME: "Renamed bus"})

    assert await current.async_step_reconfigure() == {"type": "form"}
    assert current.async_show_form.call_args.kwargs["description_placeholders"] == {
        "transport": TRANSPORT_SERIAL
    }

    with patch("custom_components.hisense_b544.config_flow._async_probe") as probe:
        assert await current.async_step_reconfigure(updated) == {"type": "abort"}

    data = {**updated, CONF_TRANSPORT: TRANSPORT_SERIAL}
    probe.assert_not_called()
    current.async_update_and_abort.assert_called_once_with(
        entry,
        unique_id="serial:/dev/serial/by-id/b544",
        title="Renamed bus",
        data=data,
    )


@pytest.mark.asyncio
async def test_empty_bus_reconfigure_skips_probe_and_updates():
    """An empty bus has no slave available for connection validation."""
    entry = make_bus_entry()
    current = config_flow()
    current._get_reconfigure_entry = MagicMock(return_value=entry)
    current.async_update_and_abort = MagicMock(return_value={"type": "abort"})
    current.hass.config_entries.async_entry_for_domain_unique_id.return_value = entry

    with patch("custom_components.hisense_b544.config_flow._async_probe") as probe:
        assert await current.async_step_reconfigure(serial_bus_input()) == {"type": "abort"}
    probe.assert_not_called()


@pytest.mark.asyncio
async def test_bus_reconfigure_duplicate_is_aborted():
    """Reconfiguration cannot claim an endpoint owned by another bus."""
    entry = make_bus_entry(make_subentry())
    current = config_flow()
    current._get_reconfigure_entry = MagicMock(return_value=entry)
    duplicate = SimpleNamespace(entry_id="another-bus")
    current.hass.config_entries.async_entry_for_domain_unique_id.return_value = duplicate
    with pytest.raises(AbortFlow):
        await current.async_step_reconfigure(serial_bus_input())
