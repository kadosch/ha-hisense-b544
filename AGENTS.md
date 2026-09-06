# AGENTS.md — Hisense B544(E)

## Purpose

`hisense_b544` is a community Home Assistant custom integration for Hisense
B544(E) adapters over local Modbus. It supports direct serial RTU and Modbus TCP
through an RTU gateway, uses no cloud service, and is not affiliated with
Hisense.

Priorities are: protocol correctness, native Home Assistant architecture,
minimal transactions, authoritative device state, and testability.

## Non-negotiable rules

- Do not open a serial port directly with PyModbus. Use Home Assistant's public
  API: `async_get_unit`, `async_get_temporary_unit`, `ModbusSerialParams`, and
  `ModbusUnit`. Keep `"dependencies": ["modbus"]` in the manifest.
- One config entry is one physical Modbus bus. Each B544/indoor unit is a config
  subentry below that bus and creates exactly one Home Assistant Device. Do not
  create an artificial Device Registry device for the bus.
- Never implement optimistic state. After every FC05/FC06 write, perform a
  targeted authoritative confirmation read; the value returned by the device is
  truth. Periodic polling still uses the complete two-block refresh.
- Do not add speculative features, entities, or undocumented register access.
- Do not use FC0F/FC10, and do not use FC01/FC03 in v0.1.
- Give every distributed Python module, class, function, and method a concise
  Google-style docstring. Ruff enforces pydocstyle rules under
  `custom_components`; test functions are exempt because their names describe
  their behavior.

## Architecture

```text
Bus ConfigEntry -> B544 subentries -> async_get_unit() -> Coordinator -> entities
```

- `b544.py` owns protocol details and addresses; entities must not contain them.
- `models.py` owns immutable, comparable `B544State` snapshots.
- `coordinator.py` uses each subentry's configurable polling interval (default
  five seconds) with `always_update=False`.
- All entities for one subentry must share `DeviceInfo` from `entity.py`; use the
  stable subentry ID for entity and device identifiers.
- Set `unit.set_message_spacing(0.03)` for each unit. All coordinators below a
  bus share one semantic operation lock so a complete poll or write-confirm
  sequence cannot interleave with another unit's operation.

## Critical polling invariant

Every device refresh must make **exactly two requests**, in this order:

```text
FC02 read_discrete_inputs(0, 16)
FC04 read_input_registers(1, 15)
```

Never poll per entity. FC04 offsets start at IR1: `array[0]` is IR1 and
`array[14]` is IR15. Decode IR1 and IR15 with
`modbus_connection.decode.decode_int16`.

## Write confirmation invariant

After a write, do not run the complete polling refresh. Confirm only the real
read-state location: Power/Sleep/Energy Saving/Super/Mute use their respective
DI, while setpoint/mode/fan use IR2/IR7/IR8. Update the frozen snapshot with
the returned value using the coordinator; never use the requested value.

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

## Config and subentry flows

- The parent flow first chooses Serial RTU or Modbus TCP. Serial bus fields are
  bus name, serial device, and baud rate (9600/19200/38400); TCP bus fields are
  bus name, host, and port (default 502). Serial link settings are fixed at 8N1
  RTU.
- A B544 subentry stores Unit ID (1..255), device name, optional model, and its
  5..3600-second polling interval. Initial bus onboarding must continue directly
  to the first device subentry flow.
- Probe every new or reconfigured B544 with
  `async with async_get_temporary_unit(...)` and both block reads. Communication
  failures must return `cannot_connect`. Do not probe a bus reconfiguration:
  changing serial link settings while the old connection is held would conflict
  with HA's connection manager. Save the bus and let its devices reconnect after
  reload.
- Bus unique IDs are `serial:<serial-path>` and `tcp:<host>:<port>`. Subentry
  unique IDs are the Unit ID within that parent. Serial paths compare literally;
  use one consistent stable path per adapter.
- Convert polling failures to `UpdateFailed`; command failures must mark the
  coordinator unavailable and raise `HomeAssistantError`. Do not reload an
  entry on a drop.
- Serialize complete polls and write-confirm sequences across every coordinator
  on the bus. Do not rely on request-level transport locking for a multi-request
  semantic operation.
- Parent or subentry updates add, remove, or reconfigure runtime resources by
  reloading the parent config entry through its update listener.

## v0.1 scope

- Climate: OFF, COOL, HEAT, DRY, FAN_ONLY, AUTO, setpoint, and fan mode.
- Switches: Sleep, Energy Saving, Super, Mute.
- Binary sensors: Compressor, Defrost, Electric Heater status.
- Sensors: indoor temperature, outlet temperature, raw fault code.

Out of scope: swing, heater control, `hvac_action`, Air Purge, fault-code
translation, unknown registers, discovery, BACnet, and unvalidated units.
`ADT52UX4RCL8` is the only validated indoor-unit model.

## Hardware safety

- B544 serial connections use 8N1 RTU at 9600, 19200, or 38400 baud. Every
  adapter on a shared RS-485 A+/B- bus must have a unique Unit ID.
- Never run two Modbus masters on one serial port. During migration, remove only
  the old B544 YAML hub; do not touch unrelated ports/hubs.
- Reads are hardware-validated. Writes follow the manual and need physical
  validation before a stable release.

## Quality and publishing

Run before delivery:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/coverage run -m pytest -q
.venv/bin/coverage report
```

CI runs HACS validation, hassfest, ruff, pytest, and coverage (minimum 90%).
Add tests for changes to addresses, grouped reads, write order, or config flow.
Keep executable files under `custom_components/hisense_b544/`, preserve
`hacs.json`, translations, and the neutral `brand/icon.png`, and do not use
Hisense commercial logos without permission.
