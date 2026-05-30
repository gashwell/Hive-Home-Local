"""TRV Climate entity for Hive Home Local.

Supports UK7004240 / TRV001 radiator valves via Zigbee2MQTT.
Mode state machine: off / manual / schedule / boost / away / holiday.
HA is always the schedule controller — TRVs run in setpoint mode.
"""

from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_HUB,
    DEFAULT_FROST_TEMP,
    DOMAIN,
    FAMILY_TRV,
    MODE_AWAY,
    MODE_BOOST,
    MODE_HOLIDAY,
    MODE_MANUAL,
    MODE_OFF,
    MODE_SCHEDULE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TRV climate entities."""
    hub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]

    entities: list[HiveTRVClimate] = []

    def _add(coordinator) -> None:
        entity = HiveTRVClimate(coordinator)
        entities.append(entity)
        async_add_entities([entity])

    def _remove(friendly_name: str) -> None:
        for entity in list(entities):
            if entity.coordinator.friendly_name == friendly_name:
                hass.async_create_task(entity.async_remove())
                entities.remove(entity)

    hub.register_add_entities(FAMILY_TRV, _add, _remove)

    # Listen for room group add/remove
    async def _room_added(event) -> None:
        room_coord = event.data.get("coordinator")
        if room_coord:
            async_add_entities([HiveRoomClimate(room_coord)])

    hass.bus.async_listen(f"{DOMAIN}_room_added", _room_added)


PRESET_MODES = [MODE_MANUAL, MODE_SCHEDULE, MODE_BOOST]


class HiveTRVClimate(CoordinatorEntity, ClimateEntity):
    """Climate entity for a single Hive TRV."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = PRESET_MODES
    _attr_min_temp = 7.0
    _attr_max_temp = 32.0
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_has_entity_name = True

    def __init__(self, coordinator) -> None:
        """Initialise."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.ieee_address}_climate"
        self._attr_name = None  # device name IS the entity name

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.ieee_address)},
            "name": self.coordinator.friendly_name,
            "model": self.coordinator.model,
            "manufacturer": "Hive",
        }

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        mode = self.coordinator.mode
        if mode in (MODE_OFF, MODE_AWAY, MODE_HOLIDAY):
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        running = self.coordinator.data.get("running_state", "")
        if running == "heat":
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        """Return current preset."""
        mode = self.coordinator.mode
        if mode in (MODE_AWAY, MODE_HOLIDAY, MODE_OFF):
            return None
        return mode

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        raw = self.coordinator.data.get("local_temperature")
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature."""
        raw = self.coordinator.data.get("occupied_heating_setpoint")
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict:
        """Extra diagnostic and mode attributes."""
        attrs: dict = {
            "mode": self.coordinator.mode,
            "pi_heating_demand": self.coordinator.data.get("pi_heating_demand"),
            "heat_required": self.coordinator.data.get("running_state") == "heat",
            "battery": self.coordinator.data.get("battery"),
            "window_open": self.coordinator.data.get("window_open_internal"),
        }
        if self.coordinator.mode == MODE_BOOST:
            attrs["boost_ends"] = getattr(self.coordinator, "_boost_end", None)
        if self.coordinator.mode in (MODE_AWAY, MODE_HOLIDAY):
            attrs[self.coordinator.mode] = True
        return {k: v for k, v in attrs.items() if v is not None}

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set_mode(MODE_OFF)
        else:
            await self.coordinator.async_set_mode(MODE_MANUAL)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        await self.coordinator.async_set_mode(preset_mode)

    async def async_set_temperature(self, **kwargs) -> None:
        """Set target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.coordinator.async_set_manual_temperature(float(temp))

    async def async_turn_on(self) -> None:
        """Turn on (switch to manual)."""
        await self.coordinator.async_set_mode(MODE_MANUAL)

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.coordinator.async_set_mode(MODE_OFF)


class HiveRoomClimate(CoordinatorEntity, ClimateEntity):
    """Climate entity for a room group of TRVs."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = PRESET_MODES
    _attr_min_temp = 7.0
    _attr_max_temp = 32.0
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_has_entity_name = True

    def __init__(self, coordinator) -> None:
        """Initialise."""
        super().__init__(coordinator)
        self._attr_unique_id = f"room_{coordinator.room_id}_climate"
        self._attr_name = coordinator.room_name

    @property
    def device_info(self):
        """Room group device info."""
        return {
            "identifiers": {(DOMAIN, f"room_{self.coordinator.room_id}")},
            "name": self.coordinator.room_name,
            "model": "Room Group",
            "manufacturer": "Hive Home Local",
        }

    @property
    def hvac_mode(self) -> HVACMode:
        """Return HVAC mode."""
        if self.coordinator.mode in (MODE_OFF, MODE_AWAY, MODE_HOLIDAY):
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def preset_mode(self) -> str | None:
        """Return preset."""
        mode = self.coordinator.mode
        if mode in (MODE_AWAY, MODE_HOLIDAY, MODE_OFF):
            return None
        return mode

    @property
    def current_temperature(self) -> float | None:
        """Average temperature across all room sources."""
        return self.coordinator.current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Target temperature (from first active TRV)."""
        return self.coordinator.target_temperature

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        await self.coordinator.async_set_mode(
            MODE_OFF if hvac_mode == HVACMode.OFF else MODE_MANUAL
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset."""
        await self.coordinator.async_set_mode(preset_mode)

    async def async_set_temperature(self, **kwargs) -> None:
        """Set temperature on all TRVs in the room."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.coordinator.async_set_temperature(float(temp))

    async def async_turn_on(self) -> None:
        """Turn on."""
        await self.coordinator.async_set_mode(MODE_MANUAL)

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.coordinator.async_set_mode(MODE_OFF)
