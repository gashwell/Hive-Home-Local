"""Weekly schedule manager for TRVs and rooms.

Schedules are stored as a list of slots::

    [
        {"days": [0,1,2,3,4], "time": "06:30", "temperature": 20.5},
        {"days": [0,1,2,3,4], "time": "08:00", "temperature": 18.0},
        {"days": [5,6],       "time": "07:00", "temperature": 21.0},
        ...
    ]

Days: 0 = Monday … 6 = Sunday (ISO weekday - 1).

On startup (and when a schedule is saved) the manager works out which slot
is currently active and applies it, then schedules the next transition.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time as dtime, timedelta

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_point_in_time

_LOGGER = logging.getLogger(__name__)


class ScheduleManager:
    """Applies schedule slots to a target by calling *apply_fn(temperature)*."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        apply_fn: Callable[[float], Awaitable[None]],
    ) -> None:
        self.hass     = hass
        self.name     = name
        self._apply   = apply_fn
        self._schedule: list[dict[str, Any]] = []
        self._cancel: Callable | None = None

    # ── Public ────────────────────────────────────────────────────────────────

    async def async_set_schedule(self, schedule: list[dict[str, Any]]) -> None:
        self._schedule = list(schedule)
        await self._apply_current_slot()
        self._schedule_next_transition()

    def clear(self) -> None:
        self._schedule = []
        if self._cancel:
            self._cancel()
            self._cancel = None

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _apply_current_slot(self) -> None:
        slot = self._active_slot()
        if slot:
            temp = float(slot["temperature"])
            _LOGGER.debug("Schedule %s: applying %.1f °C (current slot)", self.name, temp)
            await self._apply(temp)
    async def advance_to_next(self) -> bool:
        """Skip the current slot and jump immediately to the next one.

        Returns False if there is no next slot to advance to.
        Cancels the pending transition timer, applies the next slot's temperature
        now, then schedules the transition *after* that one so the schedule
        continues naturally from that point.
        """
        if not self._schedule:
            return False

        # Cancel the pending next-transition timer before doing anything
        if self._cancel:
            self._cancel()
            self._cancel = None

        next_dt, next_temp = self._next_transition()
        if next_dt is None:
            return False

        _LOGGER.debug("Schedule %s: advancing to %.1f °C (next slot)", self.name, next_temp)
        await self._apply(next_temp)

        # Now schedule the transition *after* the one we just jumped to
        after_dt, after_temp = self._find_transition_after(next_dt)
        if after_dt is not None:
            self._schedule_at_point(after_dt, after_temp)

        return True

    def _find_transition_after(
        self, reference_utc: datetime
    ) -> tuple[datetime | None, float]:
        """Return the first transition strictly after *reference_utc*."""
        ref_local = dt_util.as_local(reference_utc)
        ref_date  = ref_local.date()
        ref_time  = ref_local.time().replace(second=0, microsecond=0)
        ref_day   = ref_local.weekday()

        for delta in range(8):
            check_day  = (ref_day + delta) % 7
            check_date = ref_date + timedelta(days=delta)
            for slot in self._schedule:
                if check_day not in slot.get("days", []):
                    continue
                slot_time = _parse_time(slot["time"])
                if delta == 0 and slot_time <= ref_time:
                    continue
                naive = datetime.combine(check_date, slot_time)
                local = dt_util.as_local(naive)
                return dt_util.as_utc(local), float(slot["temperature"])
        return None, 0.0

    def _schedule_at_point(self, utc_dt: datetime, temp: float) -> None:
        """Schedule a single one-shot transition at the given UTC datetime."""
        if self._cancel:
            self._cancel()
            self._cancel = None

        @callback_wrapper
        async def _fire(_now: datetime) -> None:
            await self._apply(temp)
            self._schedule_next_transition()

        self._cancel = async_track_point_in_time(self.hass, _fire, utc_dt)


        if self._cancel:
            self._cancel()
            self._cancel = None
        if not self._schedule:
            return

        next_dt, next_temp = self._next_transition()
        if next_dt is None:
            return

        _LOGGER.debug(
            "Schedule %s: next transition %.1f °C at %s",
            self.name, next_temp, next_dt.isoformat(),
        )

        @callback_wrapper
        async def _fire(_now: datetime) -> None:  # noqa: ARG001
            await self._apply(next_temp)
            self._schedule_next_transition()

        self._cancel = async_track_point_in_time(self.hass, _fire, next_dt)

    def _active_slot(self) -> dict | None:
        """Return the slot whose time is ≤ now on today's weekday."""
        now_local = dt_util.now()
        today = now_local.weekday()   # 0=Mon
        now_t = now_local.time().replace(second=0, microsecond=0)

        candidates = []
        for slot in self._schedule:
            if today in slot.get("days", []):
                slot_time = _parse_time(slot["time"])
                if slot_time <= now_t:
                    candidates.append((slot_time, slot))

        if not candidates:
            # Nothing today before now — look for yesterday's last slot
            yesterday = (today - 1) % 7
            for slot in self._schedule:
                if yesterday in slot.get("days", []):
                    candidates.append((_parse_time(slot["time"]), slot))

        if not candidates:
            return None
        # Latest slot ≤ now
        return max(candidates, key=lambda x: x[0])[1]

    def _next_transition(self) -> tuple[datetime | None, float]:
        """Return (utc datetime, temperature) of the next schedule transition."""
        if not self._schedule:
            return None, 0.0

        now_local = dt_util.now()
        today = now_local.weekday()
        now_t = now_local.time().replace(second=0, microsecond=0)

        # Search next 7 days
        for delta_days in range(8):
            check_day   = (today + delta_days) % 7
            check_date  = now_local.date() + timedelta(days=delta_days)
            for slot in self._schedule:
                if check_day not in slot.get("days", []):
                    continue
                slot_time = _parse_time(slot["time"])
                if delta_days == 0 and slot_time <= now_t:
                    continue    # already passed today
                naive_dt = datetime.combine(check_date, slot_time)
                local_dt = dt_util.as_local(naive_dt)
                utc_dt   = dt_util.as_utc(local_dt)
                return utc_dt, float(slot["temperature"])

        return None, 0.0


def _parse_time(t: str) -> dtime:
    h, m = t.split(":")
    return dtime(int(h), int(m))


def callback_wrapper(coro_fn):  # noqa: ANN001
    """Wrap an async function into an HA @callback-compatible listener."""
    from homeassistant.core import callback

    @callback
    def _wrapper(now: datetime) -> None:
        import asyncio
        asyncio.ensure_future(coro_fn(now))

    return _wrapper
