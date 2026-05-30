"""Presence manager — geofencing via HA person entities.

Watches a configured list of ``person.*`` entities.  When **all** persons
are away from home the manager activates away mode on all TRVs/rooms,
setting them to frost protection.  When **any** person returns home it
restores the previous mode.

Away mode is lower-priority than holiday mode — if a holiday is active,
presence changes are ignored.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DEFAULT_FROST_TEMP, MODE_AWAY, MODE_HOLIDAY, MODE_OFF

_LOGGER = logging.getLogger(__name__)

_HOME_STATES = {"home"}


class PresenceManager:
    """Watches person entities and triggers away/home mode on the TRV hub."""

    def __init__(
        self,
        hass: HomeAssistant,
        person_entity_ids: list[str],
        hub: Any,
        holiday_manager: Any,
    ) -> None:
        self.hass            = hass
        self._person_ids     = list(person_entity_ids)
        self._hub            = hub
        self._holiday_mgr    = holiday_manager
        self._away_active    = False
        self._saved_modes:   dict[str, str] = {}
        self._unsubscribe:   Callable | None = None

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        if not self._person_ids:
            return

        @callback
        def _on_state_change(event: Any) -> None:
            self.hass.async_create_task(self._evaluate())

        self._unsubscribe = async_track_state_change_event(
            self.hass, self._person_ids, _on_state_change
        )

        # Evaluate immediately at startup
        await self._evaluate()
        _LOGGER.info(
            "Presence manager watching: %s", ", ".join(self._person_ids)
        )

    async def async_unload(self) -> None:
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def anyone_home(self) -> bool:
        for eid in self._person_ids:
            state = self.hass.states.get(eid)
            if state and state.state in _HOME_STATES:
                return True
        return False

    @property
    def away_active(self) -> bool:
        return self._away_active

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _evaluate(self) -> None:
        # Holiday mode takes priority — don't interfere with it
        if self._holiday_mgr and self._holiday_mgr.is_active:
            return

        if not self.anyone_home:
            if not self._away_active:
                await self._go_away()
        else:
            if self._away_active:
                await self._come_home()

    async def _go_away(self) -> None:
        _LOGGER.info("Presence: all persons away — activating away mode")
        self._away_active = True
        self._saved_modes = {}

        for name, coord in self._hub.coordinators.items():
            self._saved_modes[name] = coord.mode
            coord._mode = MODE_AWAY
            await coord.async_set_temperature(DEFAULT_FROST_TEMP)
            coord.async_write_ha_state_for_all()

        for room_id, room_coord in self._hub._room_coordinators.items():
            self._saved_modes[f"__room__{room_id}"] = room_coord.mode
            room_coord._mode = MODE_AWAY
            await room_coord._apply_temperature(DEFAULT_FROST_TEMP)
            room_coord._refresh_data()

    async def _come_home(self) -> None:
        _LOGGER.info("Presence: someone home — restoring modes")
        self._away_active = False

        for name, coord in self._hub.coordinators.items():
            restore = self._saved_modes.get(name, MODE_OFF)
            if restore in (MODE_AWAY, MODE_HOLIDAY):
                restore = MODE_OFF
            await coord.async_set_mode(restore)

        for room_id, room_coord in self._hub._room_coordinators.items():
            restore = self._saved_modes.get(f"__room__{room_id}", MODE_OFF)
            if restore in (MODE_AWAY, MODE_HOLIDAY):
                restore = MODE_OFF
            await room_coord.async_set_mode(restore)

        self._saved_modes = {}
