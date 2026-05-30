"""Climate platform for Hive Home Local — dispatches to hub or TRV implementation."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_FAMILY, DOMAIN, FAMILY_TRV


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities for the correct device family."""
    if entry.data.get(CONF_DEVICE_FAMILY) == FAMILY_TRV:
        from .trv_climate import async_setup_entry as trv_setup
        await trv_setup(hass, entry, async_add_entities)
    else:
        from .hub_climate import async_setup_entry as hub_setup
        await hub_setup(hass, entry, async_add_entities)
