# Hisense B544(E) for Home Assistant

Local Home Assistant custom integration for Hisense B544(E) central-control adapters over Modbus RTU. It supports either a direct serial RTU connection or a Modbus TCP to RTU gateway. It does not use ConnectLife or any cloud service.

This is an independent community integration and is not affiliated with or endorsed by Hisense.

## Status

The read map has been validated with a B544 on an `ADT52UX4RCL8` indoor unit. Write commands follow the Hisense B544(E) manual and must be hardware-validated before relying on them in production.

Each physical Modbus bus is configured once, and every B544 on it is added as a device below that bus. Each periodic device polling cycle uses exactly two transactions: `FC02(0, 16)` and `FC04(1, 15)`. Commands use only FC05 or FC06, followed by targeted reads of the affected authoritative DI or IR; the integration never uses optimistic state. Because B544 readback can lag behind a successful write, stale values are retried every 200 ms for up to three seconds and are never published as command confirmation.

## Requirements

- B544(E) configured for Modbus and with a unique Unit ID.
- RS-485 wired A+ to A+ and B- to B-; follow Hisense termination/topology guidance.
- Home Assistant 2026.9.0 or newer.
- No other Modbus master may access the same serial port. Remove only the old B544 YAML hub before enabling this integration; unrelated Modbus ports can remain configured.

For direct serial RTU, the default B544 baud rate is 9600; 19200 and 38400 baud are also supported, with 8N1 RTU. Prefer a stable `/dev/serial/by-id/...` path: serial aliases are treated as distinct endpoints by the shared Modbus connection manager.

For a Modbus TCP to RTU gateway, select **Modbus TCP** in the setup flow and provide its host and port (default: 502). The gateway must expose the B544's RTU slave IDs unchanged.

## Installation

### HACS

After publication, add this repository in HACS as type **Integration**, download it, restart Home Assistant, then add **Hisense B544** under **Settings → Devices & services**.

### Manual

Copy `custom_components/hisense_b544` into `/config/custom_components/`, restart Home Assistant, and add the integration from **Settings → Devices & services**.

## Configuration

Add one integration entry per physical bus:

1. Choose **Serial RTU** for a directly connected RS-485 adapter, or **Modbus TCP** for an RTU gateway.
2. Enter the shared connection settings and a descriptive bus name.
3. Add the first B544 in the device form that opens automatically. Enter its unique Unit ID, device name, optional indoor-unit model, and polling interval.
4. Add further B544 devices from the same integration entry. Reuse the bus and assign a different Unit ID to every adapter.

The bus is a Home Assistant config entry, not an artificial Device Registry device. Each B544 subentry creates one real Home Assistant device containing its eleven entities. All units use the same Home Assistant-managed Modbus connection, and the integration serializes complete polling and write-confirm operations across the bus.

The polling interval is configured independently for each B544, defaults to 5 seconds, and accepts 5 to 3600 seconds. Reconfigure the individual B544 device to change it. Reconfigure the parent bus to change its endpoint or link settings. Bus changes are applied on reload; if the new settings are wrong, its devices become unavailable and recover after the settings are corrected.

For `N` B544 devices whose polling cycles happen at the same cadence, the bus performs `2 × N` periodic read transactions per cycle. A command adds one FC05/FC06 write and only the targeted DI/IR confirmation reads required by that command. The first matching read completes confirmation; additional targeted reads occur only while the B544 still reports its previous state.

## Entities

- Climate: power, mode, target temperature, fan mode.
- Switches: Sleep, Energy Saving, Super, Mute.
- Binary sensors: Compressor, Defrost, Electric Heater.
- Sensors: indoor temperature, outlet air temperature, raw fault code.

Swing, electric-heater control, `hvac_action`, fault-code translations, automatic slave discovery, and undocumented registers are deliberately outside v0.1.

## Troubleshooting

Enable debug logging for `custom_components.hisense_b544` when diagnosing communications. Check B544 DIP switches for Modbus protocol, baud rate, and address; verify A+/B- polarity and ensure every B544 on a bus has a different Unit ID. Only one Modbus master may own a serial interface. For TCP, confirm that the gateway forwards Modbus unit IDs and that its host and port are reachable from Home Assistant.

## Development and testing

Install the reproducible test environment and run all checks with:

```bash
python3 -m venv .venv
.venv/bin/pip install '.[test]'
GITHUB_TOKEN=... ./scripts/validate
```

The preflight runs the same checks as GitHub Actions: ruff, pytest, coverage,
actionlint, Hassfest, and the HACS Action. Docker and a GitHub token are required
because the HACS Action validates public repository metadata. It infers the
repository from `origin`; set `HACS_REPOSITORY=owner/repository` to override it.

The suite combines focused protocol unit tests with integration tests running a real in-memory Home Assistant instance. Integration-owned config flows—including frontend schema serialization and submission through Home Assistant's authenticated HTTP API—config entries, subentries, coordinators, platforms, services, state machine, Entity Registry, and Device Registry are exercised together. Only the external `ModbusUnit` boundary is replaced by a stateful fake.

## Publishing

Finishing a Git Flow release or hotfix must update `manifest.json`,
`pyproject.toml`, and `CHANGELOG.md`, then create an annotated semantic-version
tag such as `v0.2.2`. After pushing the completed `main` and `develop` branches,
push the tag:

```bash
git push origin main develop
git push origin v0.2.2
```

The tag starts the release workflow. It reuses the normal test and validation
workflows, verifies that the tag matches both stored versions, and creates the
GitHub Release with generated notes only after every gate passes. Tag pushes do
not run duplicate standalone CI workflows.
