# Changelog

## 0.1.0 - Unreleased

- Initial local Modbus integration for Hisense B544(E), using direct serial RTU
  or Modbus TCP through an RTU gateway.
- One Home Assistant device per B544, with grouped state polling and authoritative updates.
- Configurable 5-to-3600-second polling interval.
- Climate, mode switches, status binary sensors, and temperature/fault sensors.
- Immediate targeted DI/IR confirmation after every write, serialized against
  periodic polling and without optimistic state.
- HACS, hassfest, ruff, pytest, and coverage validation.
