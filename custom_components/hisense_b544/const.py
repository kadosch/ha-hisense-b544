"""Constants for the Hisense B544 integration."""

from datetime import timedelta

DOMAIN = "hisense_b544"
PLATFORMS = ("binary_sensor", "climate", "sensor", "switch")

CONF_DEVICE = "device"
CONF_BAUDRATE = "baudrate"
CONF_TRANSPORT = "transport"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_UNIT_ID = "unit_id"
CONF_NAME = "name"
CONF_MODEL = "model"

DEFAULT_BAUDRATE = 9600
DEFAULT_PORT = 502
DEFAULT_NAME = "Hisense B544"
DEFAULT_MODEL = "B544(E)"
BAUDRATES = (9600, 19200, 38400)
TRANSPORT_SERIAL = "serial"
TRANSPORT_TCP = "tcp"
TRANSPORTS = (TRANSPORT_SERIAL, TRANSPORT_TCP)
SCAN_INTERVAL = timedelta(seconds=5)
MESSAGE_SPACING = 0.03

MIN_TEMPERATURE = 18
MAX_TEMPERATURE = 32
