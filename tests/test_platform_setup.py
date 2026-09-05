"""Platform setup tests for the complete B544 device surface."""

from collections import Counter
from types import SimpleNamespace

import pytest

from custom_components.hisense_b544 import binary_sensor, climate, sensor, switch
from custom_components.hisense_b544.binary_sensor import HisenseB544BinarySensor
from custom_components.hisense_b544.climate import HisenseB544Climate
from custom_components.hisense_b544.const import CONF_MODEL, CONF_NAME, DOMAIN
from custom_components.hisense_b544.models import B544State
from custom_components.hisense_b544.sensor import HisenseB544Sensor
from custom_components.hisense_b544.switch import HisenseB544Switch


def snapshot() -> B544State:
    """Return a complete authoritative state for platform construction."""
    return B544State(
        power=True,
        sleep=False,
        electric_heater=False,
        energy_saving=False,
        defrost=False,
        compressor=True,
        super_mode=False,
        mute=False,
        indoor_temperature=21,
        target_temperature=24,
        mode_code=2,
        fan_code=0,
        swing_code=0,
        fault_code=0,
        outlet_temperature=18,
        raw_di=(False,) * 16,
        raw_ir=(0,) * 15,
    )


@pytest.mark.asyncio
async def test_all_platforms_create_exactly_one_device_and_eleven_entities():
    coordinator = SimpleNamespace(data=snapshot(), last_update_success=True)
    entry = SimpleNamespace(
        entry_id="entry-id",
        data={CONF_NAME: "ADT52 P1", CONF_MODEL: "ADT52UX4RCL8"},
        runtime_data=coordinator,
    )
    entities = []

    def add_entities(new_entities) -> None:
        entities.extend(new_entities)

    for setup in (
        climate.async_setup_entry,
        switch.async_setup_entry,
        binary_sensor.async_setup_entry,
        sensor.async_setup_entry,
    ):
        await setup(None, entry, add_entities)

    assert Counter(type(entity) for entity in entities) == {
        HisenseB544Climate: 1,
        HisenseB544Switch: 4,
        HisenseB544BinarySensor: 3,
        HisenseB544Sensor: 3,
    }
    assert len({entity.unique_id for entity in entities}) == 11
    assert all(entity.available for entity in entities)
    assert {frozenset(entity.device_info["identifiers"]) for entity in entities} == {
        frozenset({(DOMAIN, "entry-id")})
    }
    assert {entity.device_info["name"] for entity in entities} == {"ADT52 P1"}
    assert {entity.device_info["model"] for entity in entities} == {"ADT52UX4RCL8"}
