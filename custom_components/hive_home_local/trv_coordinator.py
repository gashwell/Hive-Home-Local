"""Coordinators: per-TRV state machine + hub for discovery and receiver demand."""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import (
    DEFAULT_BOOST_MINUTES,
    DEFAULT_BOOST_TEMP,
    DEFAULT_FROST_TEMP,
    MODE_MANUAL,
    MODE_OFF,
    MODE_BOOST,
    MODE_SCHEDULE,
    SUPPORTED_TRV_MODELS,
    SWEEP_INTERVAL_S,
    TOPIC_BRIDGE_DEVICES,
    TOPIC_BRIDGE_REQUEST_DEVICES,
    TOPIC_BRIDGE_RESPONSE_DEVICES,
    TOPIC_DEVICE_SET,
    TOPIC_DEVICE_STATE,
)

_LOGGER = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Per-TRV coordinator — mode state machine + boost timer
# ─────────────────────────────────────────────────────────────────────────────

class HiveTRVCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Live state + operating mode for a single TRV."""

    def __init__(
        self,
        hass: HomeAssistant,
        base_topic: str,
        friendly_name: str,
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(hass, _LOGGER, name=f"Hive TRV {friendly_name}")
        self.friendly_name = friendly_name
        self.device_info   = device_info
        self._set_topic    = TOPIC_DEVICE_SET.format(base=base_topic, name=friendly_name)
        self._state_topic  = TOPIC_DEVICE_STATE.format(base=base_topic, name=friendly_name)
        self._unsubscribe: Callable | None = None
        self.data: dict[str, Any] = {}

        # ── Mode state ───────────────────────────────────────────────────────
        self._mode: str = MODE_OFF          # off | manual | schedule | boost | away | holiday
        self._manual_setpoint: float = 20.0
        self._pre_boost_mode: str = MODE_OFF
        self._pre_boost_setpoint: float = 20.0
        self._boost_end: datetime | None = None
        self._boost_task: asyncio.Task | None = None
        self._schedule_mgr: Any = None     # attached by set_schedule service

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        @callback
        def _on_state(msg: Any) -> None:
            try:
                payload: dict[str, Any] = json.loads(msg.payload)
            except (ValueError, json.JSONDecodeError):
                return
            self.async_set_updated_data({**self.data, **payload})

        self._unsubscribe = await mqtt.async_subscribe(
            self.hass, self._state_topic, _on_state, qos=0
        )
        # Ensure TRV is in setpoint mode so HA is in full control
        await self.async_publish({"programming_operation_mode": "setpoint"})

    async def async_unload(self) -> None:
        if self._boost_task:
            self._boost_task.cancel()
        if self._unsubscribe:
            self._unsubscribe()

    # ── Mode state machine ────────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return self._mode

    async def async_set_mode(self, mode: str, setpoint: float | None = None) -> None:
        """Switch to off / manual / schedule.  Call async_start_boost for boost."""
        if mode == MODE_BOOST:
            await self.async_start_boost()
            return
        # Cancel any active boost
        if self._boost_task and not self._boost_task.done():
            self._boost_task.cancel()
            self._boost_task = None
            self._boost_end = None

        self._mode = mode
        if mode == MODE_OFF:
            await self.async_set_temperature(DEFAULT_FROST_TEMP)
        elif mode == MODE_MANUAL:
            sp = setpoint or self._manual_setpoint
            self._manual_setpoint = sp
            await self.async_set_temperature(sp)
        elif mode == MODE_SCHEDULE:
            # Schedule manager will push the right setpoint on next tick
            pass
        self.async_write_ha_state_for_all()

    async def async_set_manual_temperature(self, temp: float) -> None:
        """User moved the temperature slider while in manual mode."""
        self._manual_setpoint = temp
        if self._mode in (MODE_MANUAL, MODE_SCHEDULE):
            await self.async_set_temperature(temp)
        elif self._mode == MODE_OFF:
            # Switching to manual implicitly
            self._mode = MODE_MANUAL
            await self.async_set_temperature(temp)
        self.async_write_ha_state_for_all()

    # ── Boost ─────────────────────────────────────────────────────────────────

    async def async_start_boost(
        self,
        temperature: float | None = None,
        duration_minutes: int | None = None,
    ) -> None:
        boost_temp = temperature or DEFAULT_BOOST_TEMP
        boost_mins = duration_minutes or DEFAULT_BOOST_MINUTES

        # Save current state so we can return to it
        self._pre_boost_mode = self._mode if self._mode != MODE_BOOST else self._pre_boost_mode
        self._pre_boost_setpoint = self._manual_setpoint

        self._mode = MODE_BOOST
        self._boost_end = dt_util.utcnow() + timedelta(minutes=boost_mins)

        # Cancel any previous boost task
        if self._boost_task and not self._boost_task.done():
            self._boost_task.cancel()

        await self.async_set_temperature(boost_temp)
        self._boost_task = self.hass.async_create_task(
            self._boost_timer(boost_mins * 60)
        )
        self.async_write_ha_state_for_all()
        _LOGGER.info(
            "TRV %s boost started: %.1f °C for %d min",
            self.friendly_name, boost_temp, boost_mins
        )

    async def async_end_boost(self) -> None:
        if self._boost_task and not self._boost_task.done():
            self._boost_task.cancel()
        self._boost_task = None
        self._boost_end = None
        await self.async_set_mode(self._pre_boost_mode, self._pre_boost_setpoint)

    async def _boost_timer(self, seconds: int) -> None:
        await asyncio.sleep(seconds)
        _LOGGER.info("TRV %s boost expired, returning to %s", self.friendly_name, self._pre_boost_mode)
        self._boost_task = None
        self._boost_end = None
        await self.async_set_mode(self._pre_boost_mode, self._pre_boost_setpoint)

    @property
    def boost_end_time(self) -> datetime | None:
        return self._boost_end

    @property
    def boost_remaining_minutes(self) -> int | None:
        if self._boost_end is None:
            return None
        remaining = (self._boost_end - dt_util.utcnow()).total_seconds()
        return max(0, int(remaining / 60))

    # ── Publish helpers ───────────────────────────────────────────────────────

    async def async_publish(self, payload: dict[str, Any]) -> None:
        await mqtt.async_publish(
            self.hass, self._set_topic, json.dumps(payload), qos=0, retain=False
        )

    async def async_set_temperature(self, temp: float) -> None:
        await self.async_publish({"occupied_heating_setpoint": round(temp, 1)})

    async def async_set_heat_available(self, available: bool) -> None:
        await self.async_publish({"heat_available": available})

    async def async_push_external_temp(self, temp_c: float) -> None:
        await self.async_publish({"external_measured_room_sensor": round(temp_c * 100)})

    async def async_set_keypad_lockout(self, lock: str) -> None:
        await self.async_publish({"keypad_lockout": lock})

    async def async_set_window_open_external(self, open_: bool) -> None:
        await self.async_publish({"window_open_external": open_})

    async def async_trigger_adaptation_run(self) -> None:
        await self.async_publish({"adaptation_run_control": "initiate_adaptation"})

    async def async_set_mounted(self, mounted: bool) -> None:
        await self.async_publish({"mounted_mode_control": not mounted})

    async def async_set_regulation_offset(self, offset: float) -> None:
        await self.async_publish({"regulation_setpoint_offset": round(offset, 1)})

    # ── Convenience properties ────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def local_temperature(self) -> float | None:
        v = self.data.get("local_temperature")
        return float(v) if v is not None else None

    @property
    def setpoint(self) -> float | None:
        v = self.data.get("occupied_heating_setpoint")
        return float(v) if v is not None else None

    @property
    def heat_required(self) -> bool:
        return bool(self.data.get("heat_required", False))

    @property
    def pi_heating_demand(self) -> int | None:
        v = self.data.get("pi_heating_demand")
        return int(v) if v is not None else None

    @property
    def running_state(self) -> str:
        return self.data.get("running_state", "idle")

    @property
    def battery(self) -> int | None:
        v = self.data.get("battery")
        return int(v) if v is not None else None

    @property
    def ieee_address(self) -> str:
        return self.device_info.get("ieee_address", self.friendly_name)

    def async_write_ha_state_for_all(self) -> None:
        """Trigger HA state refresh on all listeners."""
        self.async_set_updated_data(dict(self.data))


# ─────────────────────────────────────────────────────────────────────────────
# Hub — discovery, receiver demand, boiler state broadcast
# ─────────────────────────────────────────────────────────────────────────────

class HiveTRVHub:
    """Discovers TRVs in Z2M, manages receiver demand, owns all coordinators."""

    def __init__(
        self,
        hass: HomeAssistant,
        base_topic: str,
        boiler_entity: str | None,
    ) -> None:
        self.hass          = hass
        self.base_topic    = base_topic
        self.boiler_entity = boiler_entity

        self._coordinators: dict[str, HiveTRVCoordinator] = {}

        # platform → add/remove callbacks
        self._add_cbs:    dict[str, Callable[[HiveTRVCoordinator], None]] = {}
        self._remove_cbs: dict[str, Callable[[str], None]] = {}

        # room group coordinators (populated by room.py)
        self._room_coordinators: dict[str, Any] = {}

        self._unsubscribers: list[Callable] = []
        self._sweep_task: asyncio.Task | None = None

    # ── Public ────────────────────────────────────────────────────────────────

    def register_add_entities(
        self,
        platform: str,
        add_cb: Callable[[HiveTRVCoordinator], None],
        remove_cb: Callable[[str], None],
    ) -> None:
        self._add_cbs[platform]    = add_cb
        self._remove_cbs[platform] = remove_cb
        for coord in self._coordinators.values():
            add_cb(coord)

    def register_room_coordinator(self, room_id: str, room_coord: Any) -> None:
        self._room_coordinators[room_id] = room_coord

    def unregister_room_coordinator(self, room_id: str) -> None:
        self._room_coordinators.pop(room_id, None)

    @property
    def coordinators(self) -> dict[str, HiveTRVCoordinator]:
        return dict(self._coordinators)

    def get_coordinator(self, friendly_name: str) -> HiveTRVCoordinator | None:
        return self._coordinators.get(friendly_name)

    # ── Setup / teardown ──────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        base = self.base_topic

        self._unsubscribers.append(
            await mqtt.async_subscribe(
                self.hass, TOPIC_BRIDGE_DEVICES.format(base=base),
                self._on_bridge_devices, qos=0,
            )
        )
        self._unsubscribers.append(
            await mqtt.async_subscribe(
                self.hass, TOPIC_BRIDGE_RESPONSE_DEVICES.format(base=base),
                self._on_bridge_response_devices, qos=0,
            )
        )

        # Watch boiler entity → broadcast heat_available to all TRVs
        if self.boiler_entity:
            self._unsubscribers.append(
                async_track_state_change_event(
                    self.hass, [self.boiler_entity], self._on_boiler_state_change
                )
            )

        self._sweep_task = self.hass.async_create_task(self._sweep_loop())
        _LOGGER.info("Hive TRV hub started (base: %s)", base)

    async def async_unload(self) -> None:
        if self._sweep_task:
            self._sweep_task.cancel()
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()
        for coord in self._coordinators.values():
            await coord.async_unload()
        self._coordinators.clear()

    # ── Receiver demand management ────────────────────────────────────────────

    def any_heat_required(self) -> bool:
        """Return True if any TRV or room is currently calling for heat."""
        if any(c.heat_required for c in self._coordinators.values()):
            return True
        if any(r.heat_required for r in self._room_coordinators.values()):
            return True
        return False

    async def async_evaluate_boiler_demand(self) -> None:
        """Turn boiler on/off based on aggregate heat_required."""
        if not self.boiler_entity:
            return
        needed = self.any_heat_required()
        state = self.hass.states.get(self.boiler_entity)
        if state is None:
            return
        currently_on = state.state not in ("off", "idle", "unavailable", "unknown")
        if needed and not currently_on:
            _LOGGER.debug("Heat required → turning boiler ON")
            await self._call_boiler(True)
        elif not needed and currently_on:
            _LOGGER.debug("No heat required → turning boiler OFF")
            await self._call_boiler(False)

    async def _call_boiler(self, on: bool) -> None:
        domain = self.boiler_entity.split(".")[0]
        if domain == "climate":
            from homeassistant.const import SERVICE_TURN_ON, SERVICE_TURN_OFF
            from homeassistant.components.climate import SERVICE_SET_HVAC_MODE
            from homeassistant.components.climate.const import HVACMode
            await self.hass.services.async_call(
                "climate",
                SERVICE_SET_HVAC_MODE,
                {"entity_id": self.boiler_entity,
                 "hvac_mode": HVACMode.HEAT if on else HVACMode.OFF},
                blocking=False,
            )
        else:
            service = "turn_on" if on else "turn_off"
            await self.hass.services.async_call(
                domain, service,
                {"entity_id": self.boiler_entity},
                blocking=False,
            )

    async def async_broadcast_heat_available(self, available: bool) -> None:
        for coord in self._coordinators.values():
            await coord.async_set_heat_available(available)

    @callback
    def _on_boiler_state_change(self, event: Any) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        available = new_state.state not in ("off", "idle", "unavailable", "unknown")
        self.hass.async_create_task(self.async_broadcast_heat_available(available))

    # ── Sweep loop ────────────────────────────────────────────────────────────

    async def _sweep_loop(self) -> None:
        while True:
            await asyncio.sleep(SWEEP_INTERVAL_S)
            try:
                await mqtt.async_publish(
                    self.hass,
                    TOPIC_BRIDGE_REQUEST_DEVICES.format(base=self.base_topic),
                    "", qos=0, retain=False,
                )
            except Exception:  # noqa: BLE001
                pass

    # ── MQTT callbacks ────────────────────────────────────────────────────────

    @callback
    def _on_bridge_devices(self, msg: Any) -> None:
        self._process_raw(msg.payload)

    @callback
    def _on_bridge_response_devices(self, msg: Any) -> None:
        try:
            payload = json.loads(msg.payload)
            devices = payload.get("data", {})
            if isinstance(devices, list):
                self._reconcile(devices)
            elif isinstance(devices, dict):
                inner = devices.get("value", [])
                if isinstance(inner, list):
                    self._reconcile(inner)
        except (ValueError, json.JSONDecodeError):
            pass

    def _process_raw(self, raw: str | bytes) -> None:
        try:
            devices = json.loads(raw)
            if isinstance(devices, list):
                self._reconcile(devices)
        except (ValueError, json.JSONDecodeError):
            pass

    # ── Reconciliation ────────────────────────────────────────────────────────

    def _reconcile(self, devices: list[dict[str, Any]]) -> None:
        seen: dict[str, dict] = {}
        for d in devices:
            model = (d.get("definition") or {}).get("model", "")
            if model in SUPPORTED_TRV_MODELS:
                name = d.get("friendly_name", "")
                if name:
                    seen[name] = d

        current  = set(self._coordinators)
        incoming = set(seen)

        for name in incoming - current:
            self.hass.async_create_task(self._add_trv(name, seen[name]))
        for name in current - incoming:
            self.hass.async_create_task(self._remove_trv(name))

    async def _add_trv(self, friendly_name: str, device_info: dict) -> None:
        if friendly_name in self._coordinators:
            return
        _LOGGER.info("Discovered Hive TRV: %s", friendly_name)
        coord = HiveTRVCoordinator(
            self.hass, self.base_topic, friendly_name, device_info
        )
        await coord.async_setup()
        self._coordinators[friendly_name] = coord

        # Set initial heat_available from boiler state
        if self.boiler_entity:
            state = self.hass.states.get(self.boiler_entity)
            if state:
                await coord.async_set_heat_available(
                    state.state not in ("off", "idle", "unavailable", "unknown")
                )

        # Subscribe coordinator's heat_required changes → evaluate boiler demand
        coord.async_add_listener(
            lambda: self.hass.async_create_task(self.async_evaluate_boiler_demand())
        )

        for cb in self._add_cbs.values():
            cb(coord)

    async def _remove_trv(self, friendly_name: str) -> None:
        _LOGGER.info("Hive TRV removed from Z2M: %s", friendly_name)
        coord = self._coordinators.pop(friendly_name, None)
        if coord:
            await coord.async_unload()
        for cb in self._remove_cbs.values():
            cb(friendly_name)
