"""Room group coordinator — aggregates multiple TRVs into a single virtual entity."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import (
    DEFAULT_BOOST_MINUTES,
    DEFAULT_BOOST_TEMP,
    DEFAULT_FROST_TEMP,
    MODE_BOOST,
    MODE_MANUAL,
    MODE_OFF,
    MODE_SCHEDULE,
)
from .trv_coordinator import HiveTRVCoordinator
from .trv_schedule import ScheduleManager

_LOGGER = logging.getLogger(__name__)


class HiveRoomCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Virtual coordinator for a room group.

    Commands (mode, temperature, boost) are fanned out to all member TRVs.
    Room temperature comes from the best available source:
      1. Average of configured external temperature sensor entities
      2. Average of TRV local_temperature values as fallback
    """

    def __init__(
        self,
        hass: HomeAssistant,
        room_id: str,
        room_name: str,
        trv_friendly_names: list[str],
        temp_sensor_entity_ids: list[str],
        get_trv_coordinator: Callable[[str], HiveTRVCoordinator | None],
    ) -> None:
        super().__init__(hass, _LOGGER, name=f"Hive Room {room_name}")
        self.room_id   = room_id
        self.room_name = room_name

        self._trv_names   = list(trv_friendly_names)
        self._sensor_ids  = list(temp_sensor_entity_ids)
        self._get_coord   = get_trv_coordinator

        self._mode: str        = MODE_OFF
        self._setpoint: float  = 20.0
        self._pre_boost_mode: str    = MODE_OFF
        self._pre_boost_setpoint: float = 20.0
        self._boost_end: datetime | None = None
        self._boost_task: asyncio.Task | None = None

        self._schedule_mgr = ScheduleManager(
            hass, room_name,
            lambda temp: self._apply_temperature(temp)
        )

        self._unsubscribers: list[Callable] = []
        self.data: dict[str, Any] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        """Subscribe to member TRV updates and temperature sensor changes."""
        for name in self._trv_names:
            coord = self._get_coord(name)
            if coord:
                self._unsubscribers.append(
                    coord.async_add_listener(self._on_trv_update)
                )

        if self._sensor_ids:
            self._unsubscribers.append(
                async_track_state_change_event(
                    self.hass, self._sensor_ids, self._on_sensor_update
                )
            )

        self._refresh_data()

    async def async_unload(self) -> None:
        if self._boost_task:
            self._boost_task.cancel()
        self._schedule_mgr.clear()
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def setpoint(self) -> float:
        return self._setpoint

    @property
    def current_temperature(self) -> float | None:
        """Average of ALL available temperature sources — sensors and TRV locals combined."""
        all_temps: list[float] = []

        for eid in self._sensor_ids:
            state = self.hass.states.get(eid)
            if state and state.state not in ("unavailable", "unknown"):
                try:
                    all_temps.append(float(state.state))
                except ValueError:
                    pass

        for name in self._trv_names:
            coord = self._get_coord(name)
            if coord and coord.local_temperature is not None:
                all_temps.append(coord.local_temperature)

        if not all_temps:
            return None
        return round(sum(all_temps) / len(all_temps), 1)

    @property
    def heat_required(self) -> bool:
        return any(
            (self._get_coord(n) or _NullCoord()).heat_required
            for n in self._trv_names
        )

    @property
    def boost_end_time(self) -> datetime | None:
        return self._boost_end

    @property
    def boost_remaining_minutes(self) -> int | None:
        if self._boost_end is None:
            return None
        remaining = (self._boost_end - dt_util.utcnow()).total_seconds()
        return max(0, int(remaining / 60))

    @property
    def member_trv_names(self) -> list[str]:
        return list(self._trv_names)

    @property
    def temp_sensor_ids(self) -> list[str]:
        return list(self._sensor_ids)

    # ── Mode commands ─────────────────────────────────────────────────────────

    async def async_set_mode(self, mode: str, setpoint: float | None = None) -> None:
        if mode == MODE_BOOST:
            await self.async_start_boost()
            return
        if self._boost_task and not self._boost_task.done():
            self._boost_task.cancel()
            self._boost_task = None
            self._boost_end = None

        self._mode = mode
        if mode == MODE_OFF:
            await self._apply_temperature(DEFAULT_FROST_TEMP)
        elif mode == MODE_MANUAL:
            sp = setpoint or self._setpoint
            self._setpoint = sp
            await self._apply_temperature(sp)
        elif mode == MODE_SCHEDULE:
            pass  # schedule manager pushes the setpoint
        self._refresh_data()

    async def async_set_temperature(self, temp: float) -> None:
        self._setpoint = temp
        if self._mode in (MODE_MANUAL, MODE_SCHEDULE):
            await self._apply_temperature(temp)
        elif self._mode == MODE_OFF:
            self._mode = MODE_MANUAL
            await self._apply_temperature(temp)
        self._refresh_data()

    # ── Boost ─────────────────────────────────────────────────────────────────

    async def async_start_boost(
        self,
        temperature: float | None = None,
        duration_minutes: int | None = None,
    ) -> None:
        boost_temp = temperature or DEFAULT_BOOST_TEMP
        boost_mins = duration_minutes or DEFAULT_BOOST_MINUTES

        self._pre_boost_mode    = self._mode if self._mode != MODE_BOOST else self._pre_boost_mode
        self._pre_boost_setpoint = self._setpoint
        self._mode = MODE_BOOST
        self._boost_end = dt_util.utcnow() + __import__("datetime").timedelta(minutes=boost_mins)

        if self._boost_task and not self._boost_task.done():
            self._boost_task.cancel()

        await self._apply_temperature(boost_temp)
        self._boost_task = self.hass.async_create_task(
            self._boost_timer(boost_mins * 60)
        )
        self._refresh_data()
        _LOGGER.info("Room %s boost: %.1f °C for %d min", self.room_name, boost_temp, boost_mins)

    async def async_end_boost(self) -> None:
        if self._boost_task and not self._boost_task.done():
            self._boost_task.cancel()
        self._boost_task = None
        self._boost_end  = None
        await self.async_set_mode(self._pre_boost_mode, self._pre_boost_setpoint)

    async def _boost_timer(self, seconds: int) -> None:
        await asyncio.sleep(seconds)
        self._boost_task = None
        self._boost_end  = None
        await self.async_set_mode(self._pre_boost_mode, self._pre_boost_setpoint)

    # ── Schedule ──────────────────────────────────────────────────────────────

    async def async_set_schedule(self, schedule: list[dict]) -> None:
        await self._schedule_mgr.async_set_schedule(schedule)

    def clear_schedule(self) -> None:
        self._schedule_mgr.clear()

    # ── Internals ─────────────────────────────────────────────────────────────

    async def _apply_temperature(self, temp: float) -> None:
        """Push setpoint to every member TRV."""
        for name in self._trv_names:
            coord = self._get_coord(name)
            if coord:
                await coord.async_set_temperature(temp)

    @callback
    def _on_trv_update(self) -> None:
        self._refresh_data()

    @callback
    def _on_sensor_update(self, _event: Any) -> None:
        self._refresh_data()

    def _refresh_data(self) -> None:
        self.async_set_updated_data({
            "mode":               self._mode,
            "setpoint":           self._setpoint,
            "current_temperature": self.current_temperature,
            "heat_required":      self.heat_required,
            "boost_end":          self._boost_end.isoformat() if self._boost_end else None,
        })


class _NullCoord:
    """Dummy coordinator for TRVs not yet discovered."""
    heat_required = False
    local_temperature = None
