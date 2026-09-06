"""External dependency boundaries for the Hisense B544 integration."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from homeassistant.components.modbus import async_get_temporary_unit, async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.hass_dict import HassKey
from modbus_connection import ModbusSerialParams, ModbusTcpParams, ModbusUnit

from .const import DOMAIN

type B544ModbusParams = ModbusSerialParams | ModbusTcpParams


class ModbusUnitProvider(Protocol):
    """Provide persistent and temporary units at the physical I/O boundary."""

    def get_unit(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        params: B544ModbusParams,
        unit_id: int,
    ) -> ModbusUnit:
        """Return a unit held for the lifetime of a config entry."""
        ...

    def temporary_unit(
        self,
        hass: HomeAssistant,
        params: B544ModbusParams,
        unit_id: int,
    ) -> AbstractAsyncContextManager[ModbusUnit]:
        """Return a temporary unit context for config-flow probing."""
        ...


class HomeAssistantModbusUnitProvider:
    """Provide units through Home Assistant's public shared Modbus API."""

    def get_unit(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        params: B544ModbusParams,
        unit_id: int,
    ) -> ModbusUnit:
        """Return a Home Assistant-managed persistent Modbus unit."""
        return async_get_unit(hass, entry, params, unit_id)

    def temporary_unit(
        self,
        hass: HomeAssistant,
        params: B544ModbusParams,
        unit_id: int,
    ) -> AbstractAsyncContextManager[ModbusUnit]:
        """Return a Home Assistant-managed temporary Modbus unit."""
        return async_get_temporary_unit(hass, params, unit_id)


@dataclass(frozen=True, slots=True)
class HisenseB544Dependencies:
    """Dependencies supplied at the integration composition root."""

    modbus: ModbusUnitProvider


DATA_DEPENDENCIES: HassKey[HisenseB544Dependencies] = HassKey(f"{DOMAIN}_dependencies")
DEFAULT_DEPENDENCIES = HisenseB544Dependencies(modbus=HomeAssistantModbusUnitProvider())


@callback
def get_dependencies(hass: HomeAssistant) -> HisenseB544Dependencies:
    """Return injected dependencies or the production defaults."""
    return hass.data.get(DATA_DEPENDENCIES, DEFAULT_DEPENDENCIES)


@callback
def set_dependencies(hass: HomeAssistant, dependencies: HisenseB544Dependencies) -> None:
    """Override dependencies for an isolated Home Assistant runtime."""
    hass.data[DATA_DEPENDENCIES] = dependencies
