"""Transport selection for B544 Modbus units."""

from __future__ import annotations

from modbus_connection import ModbusSerialParams, ModbusTcpParams

from .const import (
    CONF_BAUDRATE,
    CONF_DEVICE,
    CONF_HOST,
    CONF_PORT,
    CONF_TRANSPORT,
    CONF_UNIT_ID,
    TRANSPORT_SERIAL,
)


def params_from_data(data: dict) -> ModbusSerialParams | ModbusTcpParams:
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


def unique_id_from_data(data: dict) -> str:
    """Return a stable per-unit identity for the selected transport."""
    params = params_from_data(data)
    if isinstance(params, ModbusSerialParams):
        endpoint = params.device
    else:
        endpoint = f"{params.host}:{params.port}"
    return f"{data[CONF_TRANSPORT]}:{endpoint}:{data[CONF_UNIT_ID]}"
