"""Transport selection for B544 Modbus units."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from modbus_connection import ModbusSerialParams, ModbusTcpParams

from .const import (
    CONF_BAUDRATE,
    CONF_DEVICE,
    CONF_HOST,
    CONF_PORT,
    CONF_TRANSPORT,
    TRANSPORT_SERIAL,
)


def params_from_data(data: Mapping[str, Any]) -> ModbusSerialParams | ModbusTcpParams:
    """Build public modbus-connection parameters from config-entry data."""
    if data[CONF_TRANSPORT] == TRANSPORT_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE],
            baudrate=data[CONF_BAUDRATE],
            bytesize=8,
            parity="N",
            stopbits=1,
            framer="rtu",
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


def bus_unique_id_from_data(data: Mapping[str, Any]) -> str:
    """Return the connection endpoint identity for a shared Modbus bus."""
    params = params_from_data(data)
    if isinstance(params, ModbusSerialParams):
        endpoint = params.device
    else:
        endpoint = f"{params.host}:{params.port}"
    return f"{data[CONF_TRANSPORT]}:{endpoint}"
