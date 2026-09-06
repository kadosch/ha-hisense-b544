"""Config-flow tests through Home Assistant's real flow managers."""

from homeassistant.config_entries import SOURCE_USER, FlowType
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from modbus_connection import ModbusConnectionError

from custom_components.hisense_b544.const import (
    CONF_BAUDRATE,
    CONF_DEVICE,
    CONF_MODEL,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TRANSPORT,
    CONF_UNIT_ID,
    DOMAIN,
    SUBENTRY_TYPE_B544,
    TRANSPORT_SERIAL,
)
from custom_components.hisense_b544.dependencies import (
    HisenseB544Dependencies,
    set_dependencies,
)
from tests.fakes.modbus import FakeModbusUnit, FakeModbusUnitProvider


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
            CONF_BAUDRATE: 19200,
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
