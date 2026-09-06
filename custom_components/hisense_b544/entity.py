"""Shared entity support."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MODEL, CONF_NAME, DOMAIN
from .coordinator import HisenseB544Coordinator


class HisenseB544Entity(CoordinatorEntity[HisenseB544Coordinator]):
    """Base entity belonging to a single configured indoor unit."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HisenseB544Coordinator, entry) -> None:
        """Initialize a B544 entity and its shared device information."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer="Hisense",
            model=entry.data.get(CONF_MODEL) or "B544(E)",
        )
