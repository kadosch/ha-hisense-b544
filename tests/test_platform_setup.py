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
async def test_all_platforms_create_eleven_entities_per_device_subentry():
    subentries = {
        "device-a": SimpleNamespace(
            subentry_id="device-a",
            data={CONF_NAME: "Unit A", CONF_MODEL: "ADT52UX4RCL8"},
        ),
        "device-b": SimpleNamespace(
            subentry_id="device-b",
            data={CONF_NAME: "Unit B", CONF_MODEL: ""},
        ),
    }
    entry = SimpleNamespace(
        subentries=subentries,
        runtime_data=SimpleNamespace(
            coordinators={
                subentry_id: SimpleNamespace(data=snapshot(), last_update_success=True)
                for subentry_id in subentries
            }
        ),
    )
    entities = []
    registrations = []

    def add_entities(new_entities, *, config_subentry_id) -> None:
        added = list(new_entities)
        entities.extend(added)
        registrations.extend((entity, config_subentry_id) for entity in added)

    for setup in (
        climate.async_setup_entry,
        switch.async_setup_entry,
        binary_sensor.async_setup_entry,
        sensor.async_setup_entry,
    ):
        await setup(None, entry, add_entities)

    assert Counter(type(entity) for entity in entities) == {
        HisenseB544Climate: 2,
        HisenseB544Switch: 8,
        HisenseB544BinarySensor: 6,
        HisenseB544Sensor: 6,
    }
    assert len(entities) == 22
    assert len({entity.unique_id for entity in entities}) == 22
    assert all(entity.available for entity in entities)
    assert {frozenset(entity.device_info["identifiers"]) for entity in entities} == {
        frozenset({(DOMAIN, "device-a")}),
        frozenset({(DOMAIN, "device-b")}),
    }
    assert {entity.device_info["name"] for entity in entities} == {"Unit A", "Unit B"}
    assert {entity.device_info["model"] for entity in entities} == {
        "ADT52UX4RCL8",
        "B544(E)",
    }
    assert all(
        entity.unique_id.startswith(config_subentry_id)
        for entity, config_subentry_id in registrations
    )
