"""Config-flow tests through Home Assistant's real flow managers."""

import pytest
from homeassistant.config_entries import SOURCE_USER, FlowType
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from modbus_connection import ModbusConnectionError

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
    DOMAIN,
    SUBENTRY_TYPE_B544,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from custom_components.hisense_b544.dependencies import (
    HisenseB544Dependencies,
    set_dependencies,
)
from tests.fakes.modbus import FakeModbusUnit, FakeModbusUnitProvider


async def test_frontend_api_round_trips_generated_transport_option(
    hass: HomeAssistant,
    hass_client,
) -> None:
    """The HTTP API must serialize and accept every form in initial onboarding."""
    provider = FakeModbusUnitProvider({1: FakeModbusUnit()})
    set_dependencies(hass, HisenseB544Dependencies(modbus=provider))
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "config", {})
    client = await hass_client()
    response = await client.post(
        "/api/config/config_entries/flow",
        json={"handler": DOMAIN},
    )
    assert response.status == 200
    result = await response.json()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    assert result["data_schema"] == [
        {
            "selector": {
                "select": {
                    "options": ["serial", "tcp"],
                    "mode": "dropdown",
                    "translation_key": "transport",
                    "multiple": False,
                    "custom_value": False,
                    "sort": False,
                }
            },
            "name": CONF_TRANSPORT,
            "required": True,
            "default": TRANSPORT_SERIAL,
        }
    ]

    generated_option = result["data_schema"][0]["selector"]["select"]["options"][0]
    response = await client.post(
        f"/api/config/config_entries/flow/{result['flow_id']}",
        json={CONF_TRANSPORT: generated_option},
    )
    assert response.status == 200
    result = await response.json()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == TRANSPORT_SERIAL
    assert result["errors"] == {}

    schemas = {field["name"]: field for field in result["data_schema"]}
    assert schemas[CONF_NAME]["selector"] == {"text": {"multiline": False, "multiple": False}}
    assert schemas[CONF_DEVICE]["selector"] == {"text": {"multiline": False, "multiple": False}}
    assert schemas[CONF_BAUDRATE]["selector"]["select"]["options"] == [
        "9600",
        "19200",
        "38400",
    ]

    response = await client.post(
        f"/api/config/config_entries/flow/{result['flow_id']}",
        json={
            CONF_NAME: " ",
            CONF_DEVICE: " ",
            CONF_BAUDRATE: "19200",
        },
    )
    assert response.status == 200
    result = await response.json()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {
        CONF_NAME: "invalid_name",
        CONF_DEVICE: "invalid_device",
    }

    response = await client.post(
        f"/api/config/config_entries/flow/{result['flow_id']}",
        json={
            CONF_NAME: " Test bus ",
            CONF_DEVICE: " /dev/serial/by-id/test-rs485 ",
            CONF_BAUDRATE: "19200",
        },
    )
    assert response.status == 200
    result = await response.json()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_get_entry(result["result"]["entry_id"])
    assert entry is not None
    assert entry.data == {
        CONF_NAME: "Test bus",
        CONF_DEVICE: "/dev/serial/by-id/test-rs485",
        CONF_BAUDRATE: 19200,
        CONF_TRANSPORT: TRANSPORT_SERIAL,
    }

    flow_type, subentry_flow_id = result["next_flow"]
    assert flow_type == FlowType.CONFIG_SUBENTRIES_FLOW
    response = await client.get(f"/api/config/config_entries/subentries/flow/{subentry_flow_id}")
    assert response.status == 200
    result = await response.json()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert {field["name"] for field in result["data_schema"]} == {
        CONF_UNIT_ID,
        CONF_NAME,
        CONF_MODEL,
        CONF_SCAN_INTERVAL,
    }

    response = await client.post(
        f"/api/config/config_entries/subentries/flow/{subentry_flow_id}",
        json={
            CONF_UNIT_ID: 1,
            CONF_NAME: " ",
            CONF_MODEL: "",
            CONF_SCAN_INTERVAL: 30,
        },
    )
    assert response.status == 200
    result = await response.json()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_NAME: "invalid_name"}

    response = await client.post(
        f"/api/config/config_entries/subentries/flow/{subentry_flow_id}",
        json={
            CONF_UNIT_ID: 1,
            CONF_NAME: " Unit A ",
            CONF_MODEL: " ADT52UX4RCL8 ",
            CONF_SCAN_INTERVAL: 30,
        },
    )
    assert response.status == 200
    result = await response.json()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_B544)
    assert len(subentries) == 1
    assert subentries[0].data == {
        CONF_UNIT_ID: 1,
        CONF_NAME: "Unit A",
        CONF_MODEL: "ADT52UX4RCL8",
        CONF_SCAN_INTERVAL: 30,
    }


@pytest.mark.parametrize(
    ("transport", "expected_fields", "bus_input", "expected_data"),
    [
        (
            TRANSPORT_SERIAL,
            {CONF_NAME, CONF_DEVICE, CONF_BAUDRATE},
            {
                CONF_NAME: "Serial bus",
                CONF_DEVICE: "/dev/serial/by-id/another-rs485",
                CONF_BAUDRATE: "9600",
            },
            {
                CONF_NAME: "Serial bus",
                CONF_DEVICE: "/dev/serial/by-id/another-rs485",
                CONF_BAUDRATE: 9600,
                CONF_TRANSPORT: TRANSPORT_SERIAL,
            },
        ),
        (
            TRANSPORT_TCP,
            {CONF_NAME, CONF_HOST, CONF_PORT},
            {CONF_NAME: "TCP bus", CONF_HOST: "gateway.local", CONF_PORT: 1502},
            {
                CONF_NAME: "TCP bus",
                CONF_HOST: "gateway.local",
                CONF_PORT: 1502,
                CONF_TRANSPORT: TRANSPORT_TCP,
            },
        ),
    ],
)
async def test_frontend_api_serializes_each_transport_form(
    hass: HomeAssistant,
    hass_client,
    transport: str,
    expected_fields: set[str],
    bus_input: dict[str, object],
    expected_data: dict[str, object],
) -> None:
    """Both transport choices must serialize, submit, and persist correctly."""
    set_dependencies(
        hass,
        HisenseB544Dependencies(modbus=FakeModbusUnitProvider({})),
    )
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "config", {})
    client = await hass_client()
    response = await client.post(
        "/api/config/config_entries/flow",
        json={"handler": DOMAIN},
    )
    result = await response.json()

    response = await client.post(
        f"/api/config/config_entries/flow/{result['flow_id']}",
        json={CONF_TRANSPORT: transport},
    )
    assert response.status == 200
    result = await response.json()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == transport
    assert {field["name"] for field in result["data_schema"]} == expected_fields

    response = await client.post(
        f"/api/config/config_entries/flow/{result['flow_id']}",
        json=bus_input,
    )
    assert response.status == 200
    result = await response.json()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_get_entry(result["result"]["entry_id"])
    assert entry is not None
    assert entry.data == expected_data


async def test_real_flow_managers_create_bus_then_device_subentry(
    hass: HomeAssistant,
) -> None:
    """Initial onboarding should persist a bus and its first probed device."""
    provider = FakeModbusUnitProvider({1: FakeModbusUnit()})
    set_dependencies(hass, HisenseB544Dependencies(modbus=provider))

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRANSPORT: TRANSPORT_SERIAL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test bus",
            CONF_DEVICE: "/dev/serial/by-id/test-rs485",
            CONF_BAUDRATE: "19200",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.data == {
        CONF_NAME: "Test bus",
        CONF_DEVICE: "/dev/serial/by-id/test-rs485",
        CONF_BAUDRATE: 19200,
        CONF_TRANSPORT: TRANSPORT_SERIAL,
    }
    assert result["next_flow"][0] is FlowType.CONFIG_SUBENTRIES_FLOW

    provider.units[1].read_error = ModbusConnectionError("offline")
    subentry_result = await hass.config_entries.subentries.async_configure(
        result["next_flow"][1],
        {
            CONF_UNIT_ID: 1,
            CONF_NAME: "Unit A",
            CONF_MODEL: "ADT52UX4RCL8",
            CONF_SCAN_INTERVAL: 30,
        },
    )
    assert subentry_result["type"] is FlowResultType.FORM
    assert subentry_result["errors"] == {"base": "cannot_connect"}

    subentry_result = await hass.config_entries.subentries.async_configure(
        subentry_result["flow_id"],
        {
            CONF_UNIT_ID: 1,
            CONF_NAME: "Unit A",
            CONF_MODEL: "ADT52UX4RCL8",
            CONF_SCAN_INTERVAL: 30,
        },
    )
    assert subentry_result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_B544)
    assert len(subentries) == 1
    assert subentries[0].title == "Unit A"
    assert subentries[0].unique_id == "1"
    assert subentries[0].data[CONF_SCAN_INTERVAL] == 30
    assert [call[2] for call in provider.temporary_calls] == [1, 1]
    assert provider.units[1].calls == [
        ("read_discrete_inputs", 0, 16),
        ("read_discrete_inputs", 0, 16),
        ("read_input_registers", 1, 15),
        ("read_discrete_inputs", 0, 16),
        ("read_input_registers", 1, 15),
    ]
    assert set(entry.runtime_data.coordinators) == {subentries[0].subentry_id}
    assert len(er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)) == 11

    duplicate_flow = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_B544),
        context={"source": SOURCE_USER},
    )
    duplicate_result = await hass.config_entries.subentries.async_configure(
        duplicate_flow["flow_id"],
        {
            CONF_UNIT_ID: 1,
            CONF_NAME: "Duplicate",
            CONF_MODEL: "B544(E)",
            CONF_SCAN_INTERVAL: 5,
        },
    )
    assert duplicate_result["type"] is FlowResultType.ABORT
    assert duplicate_result["reason"] == "already_configured"
