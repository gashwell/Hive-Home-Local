"""TRV button entities for Hive Home Local."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_HUB, DOMAIN, FAMILY_TRV


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TRV button entities."""
    hub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]

    def _add(coordinator) -> None:
        async_add_entities([
            HiveTRVAdaptationButton(coordinator),
            HiveTRVMountingButton(coordinator),
        ])

    hub.register_add_entities(f"{FAMILY_TRV}_button", _add, lambda name: None)


class HiveTRVAdaptationButton(CoordinatorEntity, ButtonEntity):
    """Trigger valve adaptation (calibration) routine."""
    _attr_icon = "mdi:cog-refresh"
    _attr_has_entity_name = True
    _attr_name = "Run Adaptation"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.ieee_address}_adaptation"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.ieee_address)}}

    async def async_press(self) -> None:
        await self.coordinator.async_publish({"adaptation_run_control": "initiate_adaptation"})


class HiveTRVMountingButton(CoordinatorEntity, ButtonEntity):
    """Enter mounting mode for valve re-installation."""
    _attr_icon = "mdi:wrench"
    _attr_has_entity_name = True
    _attr_name = "Enter Mounting Mode"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.ieee_address}_mounting"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.ieee_address)}}

    async def async_press(self) -> None:
        await self.coordinator.async_publish({"mounted_mode_control": True})
