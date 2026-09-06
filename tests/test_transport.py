"""Transport parameter and identity tests."""

from modbus_connection import ModbusSerialParams, ModbusTcpParams

from custom_components.hisense_b544.const import (
    CONF_BAUDRATE,
    CONF_DEVICE,
    CONF_HOST,
    CONF_PORT,
    CONF_TRANSPORT,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from custom_components.hisense_b544.transport import bus_unique_id_from_data, params_from_data


def test_serial_transport_parameters_and_identity():
    data = {
        CONF_TRANSPORT: TRANSPORT_SERIAL,
        CONF_DEVICE: "/dev/serial/by-id/b544",
        CONF_BAUDRATE: 19200,
    }
    assert params_from_data(data) == ModbusSerialParams(
        device="/dev/serial/by-id/b544",
        baudrate=19200,
        bytesize=8,
        parity="N",
        stopbits=1,
        framer="rtu",
    )
    assert bus_unique_id_from_data(data) == "serial:/dev/serial/by-id/b544"


def test_tcp_transport_parameters_and_identity():
    data = {
        CONF_TRANSPORT: TRANSPORT_TCP,
        CONF_HOST: "192.0.2.10",
        CONF_PORT: 1502,
    }
    assert params_from_data(data) == ModbusTcpParams(host="192.0.2.10", port=1502)
    assert bus_unique_id_from_data(data) == "tcp:192.0.2.10:1502"


def test_tcp_identity_uses_the_connection_library_host_normalization():
    data = {
        CONF_TRANSPORT: TRANSPORT_TCP,
        CONF_HOST: "Gateway.LOCAL",
        CONF_PORT: 502,
    }

    assert bus_unique_id_from_data(data) == "tcp:gateway.local:502"
