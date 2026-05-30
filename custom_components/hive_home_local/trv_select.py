"""TRV select entities for Hive Home Local."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_HUB, DOMAIN, FAMILY_TRV

KEYPAD_OPTIONS = ["unlock", "lock1", "lock2"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TRV select entities."""
    hub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]

    def _add(coordinator) -> None:
        async_add_entities([HiveTRVKeypadSelect(coordinator)])

    hub.register_add_entities(f"{FAMILY_TRV}_select", _add, lambda name: None)


class HiveTRVKeypadSelect(CoordinatorEntity, SelectEntity):
    """Keypad lockout select."""
    _attr_options = KEYPAD_OPTIONS
    _attr_icon = "mdi:lock"
    _attr_has_entity_name = True
    _attr_name = "Keypad Lock"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.ieee_address}_keypad"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.ieee_address)}}

    @property
    def current_option(self) -> str:
        return self.coordinator.data.get("keypad_lockout", "unlock")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_publish({"keypad_lockout": option})
