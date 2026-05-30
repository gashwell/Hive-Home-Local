"""Hive Home Local — unified local integration for Hive heating devices.

Supports two device families via Zigbee2MQTT and MQTT:
  - Hub (SLR1 / SLR2 / OTR1): heating + hot water control
  - TRV (UK7004240 / TRV001): individual radiator valve control

No Hive cloud required.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
import voluptuous as vol

from .const import (
    CONF_DEVICE_FAMILY,
    DATA_HUB,
    DATA_STORE,
    DOMAIN,
    FAMILY_HUB,
    FAMILY_TRV,
    LOGGER,
    SERVICE_ADD_ROOM,
    SERVICE_ADVANCE_TRV_SCHEDULE,
    SERVICE_BOOST_HEATING,
    SERVICE_BOOST_TRV,
    SERVICE_BOOST_WATER,
    SERVICE_CANCEL_BOOST_HEATING,
    SERVICE_CANCEL_BOOST_WATER,
    SERVICE_CANCEL_HOLIDAY,
    SERVICE_CLEAR_TRV_SCHEDULE,
    SERVICE_END_BOOST_TRV,
    SERVICE_REMOVE_ROOM,
    SERVICE_SET_HOLIDAY,
    SERVICE_SET_TRV_SCHEDULE,
)

# ── Platform lists per family ─────────────────────────────────────────
HUB_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]

TRV_PLATFORMS = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hive Home Local from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    family = entry.data.get(CONF_DEVICE_FAMILY, FAMILY_HUB)

    if family == FAMILY_TRV:
        return await _setup_trv(hass, entry)
    return await _setup_hub(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    family = entry.data.get(CONF_DEVICE_FAMILY, FAMILY_HUB)
    platforms = TRV_PLATFORMS if family == FAMILY_TRV else HUB_PLATFORMS

    unloaded = await hass.config_entries.async_unload_platforms(entry, platforms)

    if unloaded and entry.entry_id in hass.data.get(DOMAIN, {}):
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, {})
        hub = entry_data.get(DATA_HUB)
        if hub and hasattr(hub, "async_unload"):
            await hub.async_unload()

    return unloaded


# ── TRV setup ─────────────────────────────────────────────────────────

async def _setup_trv(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TRV device family."""
    from .storage import HiveTRVStore
    from .trv_hub import HiveTRVHub

    store = HiveTRVStore(hass, entry.entry_id)
    await store.async_load()

    hub = HiveTRVHub(hass, entry, store)
    await hub.async_setup()

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_HUB: hub,
        DATA_STORE: store,
    }

    await hass.config_entries.async_forward_entry_setups(entry, TRV_PLATFORMS)
    _register_trv_services(hass)
    return True


def _register_trv_services(hass: HomeAssistant) -> None:
    """Register TRV services (idempotent — checks before registering)."""
    if hass.services.has_service(DOMAIN, SERVICE_BOOST_TRV):
        return

    async def _boost_trv(call: ServiceCall) -> None:
        coordinator = _resolve_trv_coordinator(hass, call.data["entity_id"])
        if coordinator:
            await coordinator.async_start_boost(
                call.data.get("temperature"),
                call.data.get("duration"),
            )

    async def _end_boost_trv(call: ServiceCall) -> None:
        coordinator = _resolve_trv_coordinator(hass, call.data["entity_id"])
        if coordinator:
            await coordinator.async_end_boost()

    async def _set_schedule(call: ServiceCall) -> None:
        coordinator = _resolve_trv_coordinator(hass, call.data["entity_id"])
        if coordinator and hasattr(coordinator, "_schedule_mgr") and coordinator._schedule_mgr:
            await coordinator._schedule_mgr.async_set_schedule(call.data["schedule"])

    async def _clear_schedule(call: ServiceCall) -> None:
        coordinator = _resolve_trv_coordinator(hass, call.data["entity_id"])
        if coordinator and hasattr(coordinator, "_schedule_mgr") and coordinator._schedule_mgr:
            coordinator._schedule_mgr = None

    async def _advance_schedule(call: ServiceCall) -> None:
        coordinator = _resolve_trv_coordinator(hass, call.data["entity_id"])
        if coordinator and hasattr(coordinator, "_schedule_mgr") and coordinator._schedule_mgr:
            await coordinator._schedule_mgr.advance_to_next()

    async def _set_holiday(call: ServiceCall) -> None:
        for entry_id, data in hass.data[DOMAIN].items():
            hub = data.get(DATA_HUB)
            if hub and hasattr(hub, "_holiday_mgr"):
                await hub._holiday_mgr.async_set_holiday(
                    call.data["departure"], call.data["return"]
                )

    async def _cancel_holiday(call: ServiceCall) -> None:
        for entry_id, data in hass.data[DOMAIN].items():
            hub = data.get(DATA_HUB)
            if hub and hasattr(hub, "_holiday_mgr"):
                await hub._holiday_mgr.async_cancel_holiday()

    async def _add_room(call: ServiceCall) -> None:
        for entry_id, data in hass.data[DOMAIN].items():
            hub = data.get(DATA_HUB)
            if hub and hasattr(hub, "async_add_room"):
                await hub.async_add_room(
                    call.data["room_name"],
                    call.data.get("trv_entity_ids", []),
                    call.data.get("temp_sensor_entity_ids", []),
                )

    async def _remove_room(call: ServiceCall) -> None:
        for entry_id, data in hass.data[DOMAIN].items():
            hub = data.get(DATA_HUB)
            if hub and hasattr(hub, "async_remove_room"):
                await hub.async_remove_room(call.data["room_name"])

    hass.services.async_register(DOMAIN, SERVICE_BOOST_TRV, _boost_trv,
        schema=vol.Schema({vol.Required("entity_id"): str,
                           vol.Optional("temperature"): vol.Coerce(float),
                           vol.Optional("duration"): vol.All(int, vol.Range(min=1, max=1440))}))
    hass.services.async_register(DOMAIN, SERVICE_END_BOOST_TRV, _end_boost_trv,
        schema=vol.Schema({vol.Required("entity_id"): str}))
    hass.services.async_register(DOMAIN, SERVICE_SET_TRV_SCHEDULE, _set_schedule,
        schema=vol.Schema({vol.Required("entity_id"): str, vol.Required("schedule"): list}))
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_TRV_SCHEDULE, _clear_schedule,
        schema=vol.Schema({vol.Required("entity_id"): str}))
    hass.services.async_register(DOMAIN, SERVICE_ADVANCE_TRV_SCHEDULE, _advance_schedule,
        schema=vol.Schema({vol.Required("entity_id"): str}))
    hass.services.async_register(DOMAIN, SERVICE_SET_HOLIDAY, _set_holiday,
        schema=vol.Schema({vol.Required("departure"): str, vol.Required("return"): str}))
    hass.services.async_register(DOMAIN, SERVICE_CANCEL_HOLIDAY, _cancel_holiday,
        schema=vol.Schema({}))
    hass.services.async_register(DOMAIN, SERVICE_ADD_ROOM, _add_room,
        schema=vol.Schema({vol.Required("room_name"): str,
                           vol.Optional("trv_entity_ids"): [str],
                           vol.Optional("temp_sensor_entity_ids"): [str]}))
    hass.services.async_register(DOMAIN, SERVICE_REMOVE_ROOM, _remove_room,
        schema=vol.Schema({vol.Required("room_name"): str}))


def _resolve_trv_coordinator(hass: HomeAssistant, entity_id: str):
    """Find the TRV coordinator for a climate entity_id."""
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        hub = data.get(DATA_HUB)
        if hub and hasattr(hub, "_coordinators"):
            for name, coord in hub._coordinators.items():
                if hasattr(coord, "entity_id") and coord.entity_id == entity_id:
                    return coord
    return None


# ── Hub setup ─────────────────────────────────────────────────────────

async def _setup_hub(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SLR/OTR hub device family (from andrew-codechimp/HA-Hive-Local-Thermostat)."""
    from .hub_coordinator import HiveHubCoordinator

    coordinator = HiveHubCoordinator(
        hass,
        entry.entry_id,
        entry.data["model"],
        entry.data["mqtt_topic"],
        entry.data.get("show_heat_schedule_mode", False),
        entry.data.get("show_water_schedule_mode", False),
    )

    hass.data[DOMAIN][entry.entry_id] = {DATA_HUB: coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, HUB_PLATFORMS)
    _register_hub_services(hass)
    return True


def _register_hub_services(hass: HomeAssistant) -> None:
    """Register hub (SLR/OTR) services."""
    if hass.services.has_service(DOMAIN, SERVICE_BOOST_HEATING):
        return

    async def _boost_heating(call: ServiceCall) -> None:
        coordinator = _resolve_hub_coordinator(hass, call.data.get("config_entry_id"))
        if coordinator:
            await coordinator.async_boost_heating(
                call.data.get("minutes_to_boost"),
                call.data.get("temperature_to_boost"),
            )

    async def _cancel_boost_heating(call: ServiceCall) -> None:
        coordinator = _resolve_hub_coordinator(hass, call.data.get("config_entry_id"))
        if coordinator:
            await coordinator.async_cancel_boost_heating()

    async def _boost_water(call: ServiceCall) -> None:
        coordinator = _resolve_hub_coordinator(hass, call.data.get("config_entry_id"))
        if coordinator:
            await coordinator.async_boost_water(call.data.get("minutes_to_boost"))

    async def _cancel_boost_water(call: ServiceCall) -> None:
        coordinator = _resolve_hub_coordinator(hass, call.data.get("config_entry_id"))
        if coordinator:
            await coordinator.async_cancel_boost_water()

    hass.services.async_register(DOMAIN, SERVICE_BOOST_HEATING, _boost_heating,
        schema=vol.Schema({vol.Optional("config_entry_id"): str,
                           vol.Optional("minutes_to_boost"): vol.All(int, vol.Range(min=15, max=180)),
                           vol.Optional("temperature_to_boost"): vol.All(float, vol.Range(min=5, max=32))}))
    hass.services.async_register(DOMAIN, SERVICE_CANCEL_BOOST_HEATING, _cancel_boost_heating,
        schema=vol.Schema({vol.Optional("config_entry_id"): str}))
    hass.services.async_register(DOMAIN, SERVICE_BOOST_WATER, _boost_water,
        schema=vol.Schema({vol.Optional("config_entry_id"): str,
                           vol.Optional("minutes_to_boost"): vol.All(int, vol.Range(min=15, max=180))}))
    hass.services.async_register(DOMAIN, SERVICE_CANCEL_BOOST_WATER, _cancel_boost_water,
        schema=vol.Schema({vol.Optional("config_entry_id"): str}))


def _resolve_hub_coordinator(hass: HomeAssistant, config_entry_id: str | None):
    """Find hub coordinator by config entry ID."""
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        if config_entry_id and entry_id != config_entry_id:
            continue
        hub = data.get(DATA_HUB)
        if hub and hasattr(hub, "async_boost_heating"):
            return hub
    return None
