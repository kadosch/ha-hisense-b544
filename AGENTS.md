# AGENTS.md — Hisense B544(E)

## Purpose

`hisense_b544` is a community Home Assistant custom integration for Hisense
B544(E) adapters over local Modbus RTU. It uses no cloud service and is not
affiliated with Hisense.

Priorities are: protocol correctness, native Home Assistant architecture,
minimal transactions, authoritative device state, and testability.

## Non-negotiable rules

- Do not open a serial port directly with PyModbus. Use Home Assistant's public
  API: `async_get_unit`, `async_get_temporary_unit`, `ModbusSerialParams`, and
  `ModbusUnit`. Keep `"dependencies": ["modbus"]` in the manifest.
- One config entry is one B544/indoor unit and creates exactly one Home Assistant
  Device. Entries with matching endpoint/link settings share HA's connection.
- Never implement optimistic state. After every FC05/FC06 write, call
  `await coordinator.async_request_refresh()`; the next device read is truth.
- Do not add speculative features, entities, or undocumented register access.
- Do not use FC0F/FC10, and do not use FC01/FC03 in v0.1.

## Architecture

```text
ConfigEntry -> async_get_unit() -> B544Device -> Coordinator -> entities
```

- `b544.py` owns protocol details and addresses; entities must not contain them.
- `models.py` owns immutable, comparable `B544State` snapshots.
- `coordinator.py` polls every five seconds with `always_update=False`.
- All entry entities must share `DeviceInfo` from `entity.py`.
- Set `unit.set_message_spacing(0.03)` per entry. Do not add global spacing
  without a reproducible communication issue.

## Critical polling invariant

Every device refresh must make **exactly two requests**, in this order:

```text
FC02 read_discrete_inputs(0, 16)
FC04 read_input_registers(1, 15)
```

Never poll per entity. FC04 offsets start at IR1: `array[0]` is IR1 and
`array[14]` is IR15. Decode IR1 and IR15 with
`modbus_connection.decode.decode_int16`.

## Modbus map

### FC02 reads: DI 0..15

| DI | Field |
|---:|---|
| 0 | Power |
| 3 | Sleep |
| 4 | Electric heater status |
| 9 | Energy saving |
| 10 | Defrost |
| 11 | Compressor |
| 14 | Super |
| 15 | Mute |

### FC04 reads: IR 1..15

| IR | Field |
|---:|---|
| 1 | Indoor temperature, signed int16 |
| 2 | Target temperature |
| 7 | Mode |
| 8 | Fan speed |
| 9 | Swing, not exposed in v0.1 |
| 12 | Raw fault code |
| 15 | Outlet temperature, signed int16 |

### FC05 writes

| Coil | Field |
|---:|---|
| 0 | Power |
| 3 | Sleep |
| 4 | Electric heater, not exposed in v0.1 |
| 9 | Energy saving |
| 13 | Super |
| 14 | Mute |

The asymmetric mappings are mandatory: `Coil13 -> DI14` for Super and
`Coil14 -> DI15` for Mute. Do not “correct” them.

### FC06 writes

| HR | Field |
|---:|---|
| 0 | Integer target temperature, 18..32 °C |
| 2 | Mode: FAN=0, HEAT=1, COOL=2, DRY=3, AUTO=4 |
| 3 | Fan: AUTO=0, HIGH=1, LOW=2, MIDDLE=3 |
| 4 | Swing, out of scope in v0.1 |

Read modes 5/6/7 map to `HVACMode.AUTO`. Do not infer `hvac_action` in AUTO.

## Config flow

- First choose Serial RTU or Modbus TCP. Serial fields are serial device and baud
  rate (9600/19200/38400); TCP fields are host and port (default 502). Both use
  Unit ID (1..255), name, and optional model. Serial link settings are fixed at
  8N1 RTU.
- Probe with `async with async_get_temporary_unit(...)` and both block reads.
  Communication failures must return `cannot_connect`.
- Unique IDs are `serial:<serial-path>:<unit-id>` and
  `tcp:<host>:<port>:<unit-id>`. Serial paths compare literally; do not mix
  `/dev/ttyACM*` with `/dev/serial/by-*` aliases.
- Convert Modbus failures to `UpdateFailed`; do not reload an entry on a drop.

## v0.1 scope

- Climate: OFF, COOL, HEAT, DRY, FAN_ONLY, AUTO, setpoint, and fan mode.
- Switches: Sleep, Energy Saving, Super, Mute.
- Binary sensors: Compressor, Defrost, Electric Heater status.
- Sensors: indoor temperature, outlet temperature, raw fault code.

Out of scope: swing, heater control, `hvac_action`, Air Purge, fault-code
translation, unknown registers, discovery, BACnet, TCP, and unvalidated units.
`ADT52UX4RCL8` is the only validated indoor-unit model.

## Hardware safety

- Validated setup: `/dev/ttyACM1`, 19200 baud, 8N1 RTU, Unit ID 1, five-second
  polling. B544 uses RS-485 A+/B-.
- Never run two Modbus masters on one serial port. During migration, remove only
  the old B544 YAML hub; do not touch unrelated ports/hubs.
- Reads are hardware-validated. Writes follow the manual and need physical
  validation before a stable release.

## Quality and publishing

Run before delivery:

```bash
.venv/bin/ruff check .
.venv/bin/coverage run -m pytest -q
.venv/bin/coverage report
```

CI runs HACS validation, hassfest, ruff, pytest, and coverage (minimum 75%).
Add tests for changes to addresses, grouped reads, write order, or config flow.
Keep executable files under `custom_components/hisense_b544/`, preserve
`hacs.json`, translations, and the neutral `brand/icon.png`, and do not use
Hisense commercial logos without permission.
