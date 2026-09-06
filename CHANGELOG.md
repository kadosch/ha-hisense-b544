# Changelog

## 0.1.0 - Unreleased

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
