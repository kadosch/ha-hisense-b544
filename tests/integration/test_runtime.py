"""Integration tests against a real in-memory Home Assistant runtime."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from modbus_connection import ModbusConnectionError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hisense_b544.const import (
    CONF_BAUDRATE,
    CONF_DEVICE,
    CONF_MODEL,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TRANSPORT,
    CONF_UNIT_ID,
    DOMAIN,
    MESSAGE_SPACING,
    SUBENTRY_TYPE_B544,
    TRANSPORT_SERIAL,
)
from custom_components.hisense_b544.dependencies import (
    HisenseB544Dependencies,
    set_dependencies,
)
from tests.fakes.modbus import FakeModbusUnit, FakeModbusUnitProvider


def unit_state(
    *,
    power: bool,
    indoor: int,
    target: int,
    mode: int,
    fan: int,
    outlet: int,
) -> FakeModbusUnit:
    """Build one fake unit with a representative authoritative snapshot."""
    discrete_inputs = [False] * 16
    discrete_inputs[0] = power
    discrete_inputs[4] = True
    discrete_inputs[11] = power
    input_registers = [0] * 15
    input_registers[0] = indoor
    input_registers[1] = target
    input_registers[6] = mode
    input_registers[7] = fan
    input_registers[11] = 7
    input_registers[14] = outlet
    return FakeModbusUnit(
        discrete_inputs=discrete_inputs,
        input_registers=input_registers,
    )


async def setup_bus(hass: HomeAssistant):
    """Set up a real HA config entry with two B544 subentries."""
    units = {
        1: unit_state(power=True, indoor=21, target=24, mode=2, fan=3, outlet=18),
        2: unit_state(power=False, indoor=23, target=22, mode=1, fan=0, outlet=25),
    }
    provider = FakeModbusUnitProvider(units)
    set_dependencies(hass, HisenseB544Dependencies(modbus=provider))
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Main HVAC bus",
        unique_id="serial:/dev/serial/by-id/test-rs485",
        version=2,
        data={
            CONF_TRANSPORT: TRANSPORT_SERIAL,
            CONF_DEVICE: "/dev/serial/by-id/test-rs485",
            CONF_BAUDRATE: 19200,
            CONF_NAME: "Main HVAC bus",
        },
        subentries_data=(
            {
                "subentry_id": "device-a",
                "subentry_type": SUBENTRY_TYPE_B544,
                "title": "Unit A",
                "unique_id": "1",
                "data": {
                    CONF_UNIT_ID: 1,
                    CONF_NAME: "Unit A",
                    CONF_MODEL: "ADT52UX4RCL8",
                    CONF_SCAN_INTERVAL: 30,
                },
            },
            {
                "subentry_id": "device-b",
                "subentry_type": SUBENTRY_TYPE_B544,
                "title": "Unit B",
                "unique_id": "2",
                "data": {
                    CONF_UNIT_ID: 2,
                    CONF_NAME: "Unit B",
                    CONF_MODEL: "B544(E)",
                    CONF_SCAN_INTERVAL: 60,
                },
            },
        ),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, provider


def entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    """Resolve one entity ID by its integration-owned unique ID."""
    result = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert result is not None
    return result


async def test_two_subentries_create_devices_entities_and_authoritative_states(
    hass: HomeAssistant,
) -> None:
    """The complete HA setup path should create two real device surfaces."""
    entry, provider = await setup_bus(hass)

    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entries) == 22
    assert {entity.config_subentry_id for entity in entries} == {"device-a", "device-b"}

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert len(devices) == 2
    assert {device.name for device in devices} == {"Unit A", "Unit B"}
    assert {device.model for device in devices} == {"ADT52UX4RCL8", "B544(E)"}

    climate_a = hass.states.get(entity_id(hass, CLIMATE_DOMAIN, "device-a_climate"))
    climate_b = hass.states.get(entity_id(hass, CLIMATE_DOMAIN, "device-b_climate"))
    assert climate_a is not None
    assert climate_a.state == HVACMode.COOL
    assert climate_a.attributes["current_temperature"] == 21
    assert climate_a.attributes["temperature"] == 24
    assert climate_a.attributes["fan_mode"] == "medium"
    assert climate_b is not None
    assert climate_b.state == HVACMode.OFF

    assert hass.states.get(entity_id(hass, SWITCH_DOMAIN, "device-a_sleep")).state == STATE_OFF
    assert (
        hass.states.get(entity_id(hass, SWITCH_DOMAIN, "device-a_energy_saving")).state == STATE_OFF
    )
    assert hass.states.get(entity_id(hass, SWITCH_DOMAIN, "device-a_super")).state == STATE_OFF
    assert hass.states.get(entity_id(hass, SWITCH_DOMAIN, "device-a_mute")).state == STATE_OFF
    assert (
        hass.states.get(entity_id(hass, BINARY_SENSOR_DOMAIN, "device-a_compressor")).state
        == STATE_ON
    )
    assert (
        hass.states.get(entity_id(hass, BINARY_SENSOR_DOMAIN, "device-a_defrost")).state
        == STATE_OFF
    )
    assert (
        hass.states.get(entity_id(hass, BINARY_SENSOR_DOMAIN, "device-a_electric_heater")).state
        == STATE_ON
    )
    assert (
        hass.states.get(entity_id(hass, SENSOR_DOMAIN, "device-a_indoor_temperature")).state == "21"
    )
    assert (
        hass.states.get(entity_id(hass, SENSOR_DOMAIN, "device-a_outlet_temperature")).state == "18"
    )
    assert hass.states.get(entity_id(hass, SENSOR_DOMAIN, "device-a_fault_code")).state == "7"

    assert [call[3] for call in provider.persistent_calls] == [1, 2]
    assert all(unit.spacing == MESSAGE_SPACING for unit in provider.units.values())
    assert all(
        unit.calls[:2]
        == [
            ("read_discrete_inputs", 0, 16),
            ("read_input_registers", 1, 15),
        ]
        for unit in provider.units.values()
    )


async def test_real_ha_services_execute_write_confirmation_pipeline(
    hass: HomeAssistant,
    monkeypatch,
) -> None:
    """HA climate and switch services should publish confirmed device state."""
    _entry, provider = await setup_bus(hass)
    unit = provider.units[1]
    climate_id = entity_id(hass, CLIMATE_DOMAIN, "device-a_climate")
    super_id = entity_id(hass, SWITCH_DOMAIN, "device-a_super")

    monkeypatch.setattr(
        "custom_components.hisense_b544.coordinator.COMMAND_CONFIRMATION_INTERVAL", 0
    )
    unit.readback_delay_reads = 2
    unit.calls.clear()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: climate_id, ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    assert unit.calls == [
        ("write_register", 0, 25),
        ("read_input_registers", 2, 1),
        ("read_input_registers", 2, 1),
        ("read_input_registers", 2, 1),
    ]
    assert hass.states.get(climate_id).attributes["temperature"] == 25

    unit.readback_delay_reads = 0
    unit.calls.clear()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: climate_id, ATTR_FAN_MODE: "low"},
        blocking=True,
    )
    assert unit.calls == [
        ("write_register", 3, 2),
        ("read_input_registers", 8, 1),
    ]
    assert hass.states.get(climate_id).attributes["fan_mode"] == "low"

    unit.readback_delay_reads = 2
    unit.calls.clear()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: super_id},
        blocking=True,
    )
    assert unit.calls == [
        ("write_coil", 13, True),
        ("read_discrete_inputs", 14, 1),
        ("read_discrete_inputs", 14, 1),
        ("read_discrete_inputs", 14, 1),
    ]
    assert hass.states.get(super_id).state == STATE_ON


async def test_unavailable_device_recovers_through_real_coordinator_entities(
    hass: HomeAssistant,
) -> None:
    """A coordinator failure and recovery should propagate through HA states."""
    entry, provider = await setup_bus(hass)
    coordinator = entry.runtime_data.coordinators["device-a"]
    climate_id = entity_id(hass, CLIMATE_DOMAIN, "device-a_climate")

    provider.units[1].read_error = ModbusConnectionError("offline")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(climate_id).state == STATE_UNAVAILABLE

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(climate_id).state == HVACMode.COOL


async def test_hvac_mode_service_powers_on_from_authoritative_off_state(
    hass: HomeAssistant,
) -> None:
    """A real climate service call should run the ordered mode-on sequence."""
    _entry, provider = await setup_bus(hass)
    unit = provider.units[2]
    climate_id = entity_id(hass, CLIMATE_DOMAIN, "device-b_climate")

    unit.calls.clear()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: climate_id, ATTR_HVAC_MODE: HVACMode.AUTO},
        blocking=True,
    )
    assert unit.calls == [
        ("write_register", 2, 4),
        ("write_coil", 0, True),
        ("read_discrete_inputs", 0, 1),
        ("read_input_registers", 7, 1),
    ]
    assert hass.states.get(climate_id).state == HVACMode.AUTO
    assert hass.states.get(climate_id).state not in {STATE_OFF, STATE_UNAVAILABLE}


async def test_subentry_reconfigure_and_removal_reload_real_bus_runtime(
    hass: HomeAssistant,
) -> None:
    """Subentry lifecycle changes should rebuild runtime and registry ownership."""
    entry, provider = await setup_bus(hass)
    climate_a = entity_id(hass, CLIMATE_DOMAIN, "device-a_climate")

    result = await entry.start_subentry_reconfigure_flow(hass, "device-a")
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_UNIT_ID: 1,
            CONF_NAME: "Renamed unit",
            CONF_MODEL: "ADT52UX4RCL8",
            CONF_SCAN_INTERVAL: 45,
        },
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.subentries["device-a"].title == "Renamed unit"
    assert entry.runtime_data.coordinators["device-a"].update_interval == timedelta(seconds=45)
    assert entity_id(hass, CLIMATE_DOMAIN, "device-a_climate") == climate_a
    device_a = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, "device-a"), entry.entry_id
    )
    assert device_a is not None
    assert device_a.name == "Renamed unit"
    assert provider.temporary_calls[-1][2] == 1

    assert hass.config_entries.async_remove_subentry(entry, "device-b")
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert set(entry.runtime_data.coordinators) == {"device-a"}
    registry_entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(registry_entries) == 11
    assert {entity.config_subentry_id for entity in registry_entries} == {"device-a"}
