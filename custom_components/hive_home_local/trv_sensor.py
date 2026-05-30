"""TRV sensor entities for Hive Home Local."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_HUB, DOMAIN, FAMILY_TRV


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TRV sensor entities."""
    hub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]

    def _add(coordinator) -> None:
        async_add_entities([
            HiveTRVBatterySensor(coordinator),
            HiveTRVDemandSensor(coordinator),
        ])

    hub.register_add_entities(f"{FAMILY_TRV}_sensor", _add, lambda name: None)


class HiveTRVBatterySensor(CoordinatorEntity, SensorEntity):
    """Battery level sensor."""
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_name = "Battery"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.ieee_address}_battery"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.ieee_address)}}

    @property
    def native_value(self):
        raw = self.coordinator.data.get("battery")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None


class HiveTRVDemandSensor(CoordinatorEntity, SensorEntity):
    """PI heating demand sensor (0–100%)."""
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:radiator"
    _attr_has_entity_name = True
    _attr_name = "Heating Demand"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.ieee_address}_demand"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.ieee_address)}}

    @property
    def native_value(self):
        raw = self.coordinator.data.get("pi_heating_demand")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None
