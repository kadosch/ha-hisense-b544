# Hisense B544(E) for Home Assistant

Local Home Assistant custom integration for Hisense B544(E) central-control adapters over Modbus RTU. It does not use ConnectLife or any cloud service.

This is an independent community integration and is not affiliated with or endorsed by Hisense.

## Status

The read map has been validated with a B544 on an `ADT52UX4RCL8` indoor unit. Write commands follow the Hisense B544(E) manual and must be hardware-validated before relying on them in production.

Every configured B544 is one Home Assistant device. Each polling cycle uses exactly two transactions: `FC02(0, 16)` and `FC04(1, 15)`. Commands use only FC05 or FC06, followed by a refresh; the integration never uses optimistic state.

## Requirements

- B544(E) configured for Modbus and with a unique Unit ID.
- RS-485 wired A+ to A+ and B- to B-; follow Hisense termination/topology guidance.
- Home Assistant 2026.9.0 or newer.
- No other Modbus master may access the same serial port. Remove only the old B544 YAML hub before enabling this integration; unrelated Modbus ports can remain configured.

The default B544 baud rate is 9600. This integration also supports 19200 and 38400 baud, 8N1 RTU. Prefer a stable `/dev/serial/by-id/...` path: serial aliases are treated as distinct endpoints by the shared Modbus connection manager.

## Installation

### HACS

After publication, add this repository in HACS as type **Integration**, download it, restart Home Assistant, then add **Hisense B544** under **Settings → Devices & services**.

### Manual

Copy `custom_components/hisense_b544` into `/config/custom_components/`, restart Home Assistant, and add the integration from **Settings → Devices & services**.

## Configuration

Add one entry per B544/interior unit. Entries on the same serial endpoint and link settings share Home Assistant's single physical connection.

For the validated setup: serial device `/dev/ttyACM1`, 19200 baud, Unit ID `1`, model `ADT52UX4RCL8`.

## Entities

- Climate: power, mode, target temperature, fan mode.
- Switches: Sleep, Energy Saving, Super, Mute.
- Binary sensors: Compressor, Defrost, Electric Heater.
- Sensors: indoor temperature, outlet air temperature, raw fault code.

Swing, electric-heater control, `hvac_action`, fault-code translations, discovery, TCP gateways, and undocumented registers are deliberately outside v0.1.

## Troubleshooting

Enable debug logging for `custom_components.hisense_b544` when diagnosing communications. Check B544 DIP switches for Modbus protocol, baud rate, and address; verify A+/B- polarity and ensure one master owns the serial interface.
