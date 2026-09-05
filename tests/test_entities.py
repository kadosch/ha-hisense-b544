"""Tests for entity state mapping and non-optimistic commands."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest
from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.components.sensor import SensorStateClass

from custom_components.hisense_b544.binary_sensor import (
    DESCRIPTIONS as BINARY_DESCRIPTIONS,
)
from custom_components.hisense_b544.binary_sensor import (
    HisenseB544BinarySensor,
)
from custom_components.hisense_b544.climate import HisenseB544Climate
from custom_components.hisense_b544.models import B544State
from custom_components.hisense_b544.sensor import DESCRIPTIONS as SENSOR_DESCRIPTIONS
from custom_components.hisense_b544.sensor import HisenseB544Sensor
from custom_components.hisense_b544.switch import DESCRIPTIONS as SWITCH_DESCRIPTIONS
from custom_components.hisense_b544.switch import HisenseB544Switch


def state(**changes) -> B544State:
    data = dict(
        power=True,
        sleep=False,
        electric_heater=True,
        energy_saving=False,
        defrost=False,
        compressor=True,
        super_mode=False,
        mute=True,
        indoor_temperature=21,
        target_temperature=24,
        mode_code=2,
        fan_code=3,
        swing_code=0,
        fault_code=7,
        outlet_temperature=19,
        raw_di=(False,) * 16,
        raw_ir=(0,) * 15,
    )
    data.update(changes)
    return B544State(**data)


def coordinator(snapshot: B544State):
    return SimpleNamespace(
        data=snapshot,
        device=SimpleNamespace(
            async_set_power=AsyncMock(),
            async_set_mode=AsyncMock(),
            async_set_target_temperature=AsyncMock(),
            async_set_fan=AsyncMock(),
            async_set_sleep=AsyncMock(),
            async_set_energy_saving=AsyncMock(),
            async_set_super=AsyncMock(),
            async_set_mute=AsyncMock(),
        ),
        async_confirm_power=AsyncMock(),
        async_confirm_input_register=AsyncMock(),
        async_confirm_sleep=AsyncMock(),
        async_confirm_energy_saving=AsyncMock(),
        async_confirm_super=AsyncMock(),
        async_confirm_mute=AsyncMock(),
        last_update_success=True,
    )


def bare_entity(entity_class, coord):
    entity = object.__new__(entity_class)
    entity.coordinator = coord
    return entity


def test_climate_state_maps_power_mode_fan_and_temperatures():
    entity = bare_entity(HisenseB544Climate, coordinator(state()))
    assert entity.hvac_mode is HVACMode.COOL
    assert entity.fan_mode == "medium"
    assert entity.current_temperature == 21
    assert entity.target_temperature == 24

    entity.coordinator.data = state(power=False, mode_code=1, fan_code=99)
    assert entity.hvac_mode is HVACMode.OFF
    assert entity.fan_mode is None

    entity.coordinator.data = state(mode_code=99)
    assert entity.hvac_mode is HVACMode.AUTO


def test_climate_has_registry_identity_and_declares_controls():
    coord = coordinator(state())
    entry = SimpleNamespace(entry_id="entry-id", data={"name": "ADT52 P1", "model": "ADT52UX4RCL8"})
    entity = HisenseB544Climate(coord, entry)

    assert entity.unique_id == "entry-id_climate"
    assert entity.supported_features == (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )


@pytest.mark.asyncio
async def test_climate_commands_use_targeted_confirmation_after_the_write():
    coord = coordinator(state(power=False))
    entity = bare_entity(HisenseB544Climate, coord)

    await entity.async_set_temperature(temperature=25)
    await entity.async_set_temperature()
    await entity.async_set_fan_mode("low")
    await entity.async_set_hvac_mode(HVACMode.HEAT)
    await entity.async_set_hvac_mode(HVACMode.OFF)

    coord.device.async_set_target_temperature.assert_awaited_once_with(25)
    coord.device.async_set_fan.assert_awaited_once_with(2)
    coord.device.async_set_mode.assert_awaited_once_with(1)
    coord.device.async_set_power.assert_has_awaits([call(True), call(False)])
    coord.async_confirm_input_register.assert_has_awaits(
        [call(2, "target_temperature"), call(8, "fan_code"), call(7, "mode_code")]
    )
    coord.async_confirm_power.assert_has_awaits([call(), call()])


@pytest.mark.asyncio
async def test_switches_reflect_snapshot_and_command_the_correct_helper():
    coord = coordinator(state(sleep=True, energy_saving=True, super_mode=True, mute=True))
    expected = {
        "sleep": "async_set_sleep",
        "energy_saving": "async_set_energy_saving",
        "super": "async_set_super",
        "mute": "async_set_mute",
    }
    for description in SWITCH_DESCRIPTIONS:
        entity = bare_entity(HisenseB544Switch, coord)
        entity.entity_description = description
        assert entity.is_on is True
        await entity.async_turn_off()
        getattr(coord.device, expected[description.key]).assert_awaited_once_with(False)

    coord.async_confirm_sleep.assert_awaited_once()
    coord.async_confirm_energy_saving.assert_awaited_once()
    coord.async_confirm_super.assert_awaited_once()
    coord.async_confirm_mute.assert_awaited_once()


def test_binary_and_numeric_sensors_expose_only_documented_values():
    coord = coordinator(state())
    assert {
        description.key: bare_entity(HisenseB544BinarySensor, coord)
        for description in BINARY_DESCRIPTIONS
    }
    binary_values = {}
    for description in BINARY_DESCRIPTIONS:
        entity = bare_entity(HisenseB544BinarySensor, coord)
        entity.entity_description = description
        binary_values[description.key] = entity.is_on
    assert binary_values == {"compressor": True, "defrost": False, "electric_heater": True}

    values = {}
    for description in SENSOR_DESCRIPTIONS:
        entity = bare_entity(HisenseB544Sensor, coord)
        entity.entity_description = description
        values[description.key] = entity.native_value
    assert values == {"indoor_temperature": 21, "outlet_temperature": 19, "fault_code": 7}


def test_descriptions_expose_home_assistant_registry_defaults():
    coord = coordinator(state())
    entry = SimpleNamespace(entry_id="entry-id", data={"name": "ADT52", "model": "B544"})
    entities = [
        HisenseB544BinarySensor(coord, entry, BINARY_DESCRIPTIONS[0]),
        HisenseB544Sensor(coord, entry, SENSOR_DESCRIPTIONS[0]),
        HisenseB544Switch(coord, entry, SWITCH_DESCRIPTIONS[0]),
    ]

    for entity in entities:
        assert entity.entity_registry_enabled_default is True
        assert entity.entity_registry_visible_default is True
        assert entity.entity_category is None

    assert entities[1].state_class is SensorStateClass.MEASUREMENT
