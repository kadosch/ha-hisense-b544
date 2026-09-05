"""Protocol models and mappings for Hisense B544(E)."""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class B544State:
    """Authoritative snapshot read from a B544(E)."""

    power: bool
    sleep: bool
    electric_heater: bool
    energy_saving: bool
    defrost: bool
    compressor: bool
    super_mode: bool
    mute: bool
    indoor_temperature: int
    target_temperature: int
    mode_code: int
    fan_code: int
    swing_code: int
    fault_code: int
    outlet_temperature: int
    raw_di: tuple[bool, ...]
    raw_ir: tuple[int, ...]
