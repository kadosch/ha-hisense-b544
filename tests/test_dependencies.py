"""Dependency composition tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from custom_components.hisense_b544.dependencies import (
    DEFAULT_DEPENDENCIES,
    HisenseB544Dependencies,
    HomeAssistantModbusUnitProvider,
    get_dependencies,
    set_dependencies,
)


def test_dependency_lookup_uses_production_default_and_runtime_override():
    """An isolated HA runtime can inject only the external Modbus boundary."""
    hass = SimpleNamespace(data={})
    assert get_dependencies(hass) is DEFAULT_DEPENDENCIES

    dependencies = HisenseB544Dependencies(modbus=MagicMock())
    set_dependencies(hass, dependencies)
    assert get_dependencies(hass) is dependencies


def test_production_provider_delegates_to_home_assistant_public_api():
    """The production provider must remain a thin public-API adapter."""
    provider = HomeAssistantModbusUnitProvider()
    hass = SimpleNamespace()
    entry = SimpleNamespace()
    params = SimpleNamespace()
    unit = SimpleNamespace()
    temporary = MagicMock()

    with (
        patch(
            "custom_components.hisense_b544.dependencies.async_get_unit",
            return_value=unit,
        ) as get_unit,
        patch(
            "custom_components.hisense_b544.dependencies.async_get_temporary_unit",
            return_value=temporary,
        ) as get_temporary_unit,
    ):
        assert provider.get_unit(hass, entry, params, 7) is unit
        assert provider.temporary_unit(hass, params, 7) is temporary

    get_unit.assert_called_once_with(hass, entry, params, 7)
    get_temporary_unit.assert_called_once_with(hass, params, 7)
