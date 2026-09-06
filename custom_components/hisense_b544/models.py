"""Protocol and runtime models for Hisense B544(E)."""

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import HisenseB544Coordinator


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


@dataclass(frozen=True, kw_only=True)
class HisenseB544Runtime:
    """Runtime resources shared by all B544 devices on one bus."""

    coordinators: dict[str, HisenseB544Coordinator]
    operation_lock: asyncio.Lock
