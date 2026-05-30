"""TRV number entities for Hive Home Local."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_HUB,
    DATA_STORE,
    DEFAULT_HEATING_BOOST_MINUTES,
    DEFAULT_HEATING_BOOST_TEMPERATURE,
    DOMAIN,
    FAMILY_TRV,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TRV number entities."""
    hub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]
    store = hass.data[DOMAIN][entry.entry_id][DATA_STORE]

    def _add(coordinator) -> None:
        async_add_entities([
            HiveTRVOffsetNumber(coordinator),
            HiveTRVBoostTempNumber(coordinator, store),
            HiveTRVBoostDurationNumber(coordinator, store),
        ])

    hub.register_add_entities(f"{FAMILY_TRV}_number", _add, lambda name: None)


class HiveTRVOffsetNumber(CoordinatorEntity, NumberEntity):
    """Setpoint temperature offset ±2.5°C."""
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = -2.5
    _attr_native_max_value = 2.5
    _attr_native_step = 0.1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:thermometer-lines"
    _attr_has_entity_name = True
    _attr_name = "Setpoint Offset"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.ieee_address}_offset"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.ieee_address)}}

    @property
    def native_value(self):
        return self.coordinator.data.get("regulation_setpoint_offset", 0.0)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_publish({"regulation_setpoint_offset": value})


class HiveTRVBoostTempNumber(CoordinatorEntity, NumberEntity):
    """Default boost temperature."""
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 10.0
    _attr_native_max_value = 32.0
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:thermometer"
    _attr_has_entity_name = True
    _attr_name = "Boost Temperature"

    def __init__(self, coordinator, store) -> None:
        super().__init__(coordinator)
        self._store = store
        self._attr_unique_id = f"{coordinator.ieee_address}_boost_temp"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.ieee_address)}}

    @property
    def native_value(self):
        return self._store.get_trv_boost_temperature(
            self.coordinator.friendly_name
        ) or DEFAULT_HEATING_BOOST_TEMPERATURE

    async def async_set_native_value(self, value: float) -> None:
        await self._store.async_set_trv_boost_defaults(
            self.coordinator.friendly_name, temperature=value
        )
        self.async_write_ha_state()


class HiveTRVBoostDurationNumber(CoordinatorEntity, NumberEntity):
    """Default boost duration in minutes."""
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 5
    _attr_native_max_value = 1440
    _attr_native_step = 5
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:timer"
    _attr_has_entity_name = True
    _attr_name = "Boost Duration"

    def __init__(self, coordinator, store) -> None:
        super().__init__(coordinator)
        self._store = store
        self._attr_unique_id = f"{coordinator.ieee_address}_boost_duration"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.ieee_address)}}

    @property
    def native_value(self):
        return self._store.get_trv_boost_duration(
            self.coordinator.friendly_name
        ) or DEFAULT_HEATING_BOOST_MINUTES

    async def async_set_native_value(self, value: float) -> None:
        await self._store.async_set_trv_boost_defaults(
            self.coordinator.friendly_name, duration=int(value)
        )
        self.async_write_ha_state()
