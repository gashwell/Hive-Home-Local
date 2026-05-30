"""Holiday mode manager.

Activates frost-protection on all TRVs/rooms for a configured date range,
then automatically restores the previous mode on the return datetime.

State is persisted in HiveTRVStore so it survives HA restarts.  On startup
the manager re-evaluates whether we are currently mid-holiday and re-arms
the return timer if needed.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_point_in_time

from .const import DEFAULT_FROST_TEMP, MODE_HOLIDAY, MODE_OFF

_LOGGER = logging.getLogger(__name__)

# Keys used in the store under "holiday"
_KEY_DEPARTURE = "departure"    # ISO string
_KEY_RETURN    = "return"       # ISO string
_KEY_ACTIVE    = "active"       # bool
_KEY_SAVED     = "saved_modes"  # {friendly_name: mode}


class HolidayManager:
    """Manages holiday mode across all TRVs and room groups.

    Usage::

        mgr = HolidayManager(hass, store, hub)
        await mgr.async_setup()          # called once on integration load
        await mgr.async_set_holiday(departure_dt, return_dt)
        await mgr.async_cancel_holiday()
    """

    def __init__(self, hass: HomeAssistant, store: Any, hub: Any) -> None:
        self.hass  = hass
        self._store = store
        self._hub   = hub
        self._cancel_activate: Callable | None = None
        self._cancel_return:   Callable | None = None

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        """Re-arm timers if a holiday is stored from before HA restarted."""
        data = self._get_stored()
        if not data:
            return

        departure_dt = _parse_iso(data.get(_KEY_DEPARTURE))
        return_dt    = _parse_iso(data.get(_KEY_RETURN))
        now          = dt_util.utcnow()

        if return_dt and return_dt <= now:
            # Holiday has already ended — clean up
            _LOGGER.info("Holiday: return time has passed, deactivating")
            await self._deactivate()
            return

        if data.get(_KEY_ACTIVE):
            # We're currently mid-holiday — re-arm return timer only
            _LOGGER.info("Holiday: resuming active holiday, return at %s", return_dt)
            if return_dt:
                self._arm_return(return_dt)
            return

        if departure_dt and departure_dt > now:
            # Departure is still in the future — re-arm both timers
            _LOGGER.info("Holiday: re-arming departure at %s", departure_dt)
            self._arm_departure(departure_dt, return_dt)

    # ── Public API ────────────────────────────────────────────────────────────

    async def async_set_holiday(
        self, departure_dt: datetime, return_dt: datetime
    ) -> None:
        """Schedule (or activate immediately) holiday mode for the given range."""
        # Cancel any existing holiday
        await self.async_cancel_holiday(silent=True)

        now = dt_util.utcnow()
        dep = dt_util.as_utc(departure_dt)
        ret = dt_util.as_utc(return_dt)

        if ret <= now:
            _LOGGER.warning("Holiday return time %s is in the past — ignoring", ret)
            return

        await self._store.async_save_holiday({
            _KEY_DEPARTURE: dep.isoformat(),
            _KEY_RETURN:    ret.isoformat(),
            _KEY_ACTIVE:    False,
            _KEY_SAVED:     {},
        })

        if dep <= now:
            # Departure time has already passed — activate immediately
            await self._activate(ret)
        else:
            self._arm_departure(dep, ret)

        _LOGGER.info(
            "Holiday mode scheduled: %s → %s",
            dep.isoformat(), ret.isoformat()
        )

    async def async_cancel_holiday(self, *, silent: bool = False) -> None:
        """Cancel an active or pending holiday."""
        if self._cancel_activate:
            self._cancel_activate()
            self._cancel_activate = None
        if self._cancel_return:
            self._cancel_return()
            self._cancel_return = None

        data = self._get_stored()
        if data and data.get(_KEY_ACTIVE):
            await self._deactivate()
        else:
            await self._store.async_clear_holiday()

        if not silent:
            _LOGGER.info("Holiday mode cancelled")

    @property
    def is_active(self) -> bool:
        data = self._get_stored()
        return bool(data and data.get(_KEY_ACTIVE))

    @property
    def departure(self) -> datetime | None:
        data = self._get_stored()
        return _parse_iso(data.get(_KEY_DEPARTURE)) if data else None

    @property
    def return_dt(self) -> datetime | None:
        data = self._get_stored()
        return _parse_iso(data.get(_KEY_RETURN)) if data else None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _arm_departure(self, dep: datetime, ret: datetime | None) -> None:
        async def _on_departure(_now: datetime) -> None:
            self._cancel_activate = None
            await self._activate(ret)

        from homeassistant.core import callback

        @callback
        def _cb(now: datetime) -> None:
            self.hass.async_create_task(_on_departure(now))

        self._cancel_activate = async_track_point_in_time(self.hass, _cb, dep)

    def _arm_return(self, ret: datetime) -> None:
        async def _on_return(_now: datetime) -> None:
            self._cancel_return = None
            await self._deactivate()

        from homeassistant.core import callback

        @callback
        def _cb(now: datetime) -> None:
            self.hass.async_create_task(_on_return(now))

        self._cancel_return = async_track_point_in_time(self.hass, _cb, ret)

    async def _activate(self, ret: datetime | None) -> None:
        """Save current modes, set all TRVs to holiday frost protection."""
        saved: dict[str, str] = {}

        for name, coord in self._hub.coordinators.items():
            saved[name] = coord.mode
            coord._mode = MODE_HOLIDAY
            await coord.async_set_temperature(DEFAULT_FROST_TEMP)
            coord.async_write_ha_state_for_all()

        for room_id, room_coord in self._hub._room_coordinators.items():
            saved[f"__room__{room_id}"] = room_coord.mode
            room_coord._mode = MODE_HOLIDAY
            await room_coord._apply_temperature(DEFAULT_FROST_TEMP)
            room_coord._refresh_data()

        await self._store.async_save_holiday({
            _KEY_DEPARTURE: (self.departure or dt_util.utcnow()).isoformat(),
            _KEY_RETURN:    ret.isoformat() if ret else None,
            _KEY_ACTIVE:    True,
            _KEY_SAVED:     saved,
        })

        if ret:
            self._arm_return(ret)

        _LOGGER.info("Holiday mode activated")

    async def _deactivate(self) -> None:
        """Restore saved modes after holiday ends."""
        data = self._get_stored()
        saved = (data or {}).get(_KEY_SAVED, {})

        for name, coord in self._hub.coordinators.items():
            restore = saved.get(name, MODE_OFF)
            if restore == MODE_HOLIDAY:
                restore = MODE_OFF
            await coord.async_set_mode(restore)

        for room_id, room_coord in self._hub._room_coordinators.items():
            restore = saved.get(f"__room__{room_id}", MODE_OFF)
            if restore == MODE_HOLIDAY:
                restore = MODE_OFF
            await room_coord.async_set_mode(restore)

        await self._store.async_clear_holiday()
        _LOGGER.info("Holiday mode ended — modes restored")

    def _get_stored(self) -> dict | None:
        return self._store.get_holiday()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
