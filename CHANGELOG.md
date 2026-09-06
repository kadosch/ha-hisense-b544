# Changelog

## Unreleased

- Create GitHub releases automatically from validated semantic-version tags.
- Reuse the existing test, HACS, and Hassfest workflows as release gates.
- Retry delayed authoritative DI/IR readback after writes without publishing
  stale intermediate values or performing a complete refresh.

## 0.2.2 - 2026-09-06

- Fix config-flow forms that failed frontend schema serialization after choosing
  Serial RTU or Modbus TCP.
- Use native Home Assistant selectors for all user-facing fields and normalize
  their frontend values before persisting bus or device data.
- Exercise complete Serial onboarding and both transport forms through Home
  Assistant's authenticated HTTP config-flow API.

## 0.2.1 - 2026-09-06

- Fix Home Assistant translation metadata required for B544 config subentries.
- Sort manifest metadata according to the current Hassfest requirement.
- Add a local CI-equivalent preflight for feature, hotfix, and release closure.

## 0.2.0 - 2026-09-06

- Initial local Modbus integration for Hisense B544(E), using direct serial RTU
  or Modbus TCP through an RTU gateway.
- One config entry per physical Modbus bus, with one device subentry and one
  Home Assistant device per B544.
- A bus-wide operation lock serializes complete polling and write-confirm
  sequences across Unit IDs.
- Independently configurable 5-to-3600-second polling interval per B544.
- Migration of pre-release single-device entries while preserving existing
  Device Registry and Entity Registry identifiers.
- Climate, mode switches, status binary sensors, and temperature/fault sensors.
- Immediate targeted DI/IR confirmation after every write, serialized against
  periodic polling and without optimistic state.
- HACS, hassfest, ruff, pytest, and coverage validation.
- Dependency injection at the external Modbus-unit boundary, keeping production
  access on Home Assistant's public shared connection API.
- In-memory Home Assistant integration tests covering config flows, subentries,
  registries, entity states, services, reloads, and communication recovery.
