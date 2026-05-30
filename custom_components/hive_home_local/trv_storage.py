"""Persistent storage for TRV schedules and room group configuration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)
_STORAGE_VERSION = 1
_STORAGE_KEY = "hive_home_local_{entry_id}"


class HiveTRVStore:
    """Thin wrapper around HA's Store for schedules and room config.

    Schema::

        {
          "trvs": {
            "<friendly_name>": {
              "schedule": [
                {
                  "days": [0,1,2,3,4],   # 0=Mon … 6=Sun
                  "time": "06:30",        # HH:MM
                  "temperature": 20.5
                },
                ...
              ],
              "boost_temperature": 22.0,
              "boost_duration": 30
            }
          },
          "rooms": {
            "<room_id>": {
              "name": "Living Room",
              "trvs": ["friendly_name_1", "friendly_name_2"],
              "temp_sensors": ["sensor.living_room_temp"],
              "schedule": [ ... same format ... ],
              "boost_temperature": 22.0,
              "boost_duration": 30
            }
          }
        }
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass,
            _STORAGE_VERSION,
            _STORAGE_KEY.format(entry_id=entry_id),
        )
        self._data: dict[str, Any] = {"trvs": {}, "rooms": {}}

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self._data = stored
        _LOGGER.debug("Storage loaded: %d TRV(s), %d room(s)",
                      len(self._data.get("trvs", {})),
                      len(self._data.get("rooms", {})))

    async def async_save(self) -> None:
        await self._store.async_save(self._data)

    # ── TRV helpers ───────────────────────────────────────────────────────────

    def get_trv_data(self, friendly_name: str) -> dict[str, Any]:
        return self._data["trvs"].get(friendly_name, {})

    def get_trv_schedule(self, friendly_name: str) -> list[dict]:
        return self.get_trv_data(friendly_name).get("schedule", [])

    async def async_set_trv_schedule(
        self, friendly_name: str, schedule: list[dict]
    ) -> None:
        self._data["trvs"].setdefault(friendly_name, {})["schedule"] = schedule
        await self.async_save()

    async def async_set_trv_boost_defaults(
        self, friendly_name: str, temperature: float, duration_minutes: int
    ) -> None:
        self._data["trvs"].setdefault(friendly_name, {}).update(
            {"boost_temperature": temperature, "boost_duration": duration_minutes}
        )
        await self.async_save()

    def get_trv_boost_temperature(self, friendly_name: str) -> float:
        from .const import DEFAULT_BOOST_TEMP
        return self.get_trv_data(friendly_name).get("boost_temperature", DEFAULT_BOOST_TEMP)

    def get_trv_boost_duration(self, friendly_name: str) -> int:
        from .const import DEFAULT_BOOST_MINUTES
        return self.get_trv_data(friendly_name).get("boost_duration", DEFAULT_BOOST_MINUTES)

    # ── Room helpers ──────────────────────────────────────────────────────────

    def get_all_rooms(self) -> dict[str, dict]:
        return dict(self._data.get("rooms", {}))

    def get_room(self, room_id: str) -> dict[str, Any] | None:
        return self._data["rooms"].get(room_id)

    async def async_save_room(self, room_id: str, room_data: dict[str, Any]) -> None:
        self._data["rooms"][room_id] = room_data
        await self.async_save()

    async def async_remove_room(self, room_id: str) -> None:
        self._data["rooms"].pop(room_id, None)
        await self.async_save()

    async def async_set_room_schedule(
        self, room_id: str, schedule: list[dict]
    ) -> None:
        if room_id in self._data["rooms"]:
            self._data["rooms"][room_id]["schedule"] = schedule
            await self.async_save()

    # ── Holiday helpers ───────────────────────────────────────────────────────

    def get_holiday(self) -> dict | None:
        return self._data.get("holiday") or None

    async def async_save_holiday(self, holiday_data: dict) -> None:
        self._data["holiday"] = holiday_data
        await self.async_save()

    async def async_clear_holiday(self) -> None:
        self._data.pop("holiday", None)
        await self.async_save()
