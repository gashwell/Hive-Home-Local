"""Config flow for Hive Home Local.

Initial setup is kept minimal - just enough to identify the connection.
All device-specific settings (MQTT topics, boiler entity, persons) are
configured via the Configure button after the integration is installed.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BOILER_ENTITY,
    CONF_DEVICE_FAMILY,
    CONF_MODEL,
    CONF_MQTT_TOPIC,
    CONF_PERSON_ENTITIES,
    CONF_SHOW_HEAT_SCHEDULE_MODE,
    CONF_SHOW_WATER_SCHEDULE_MODE,
    CONF_Z2M_BASE_TOPIC,
    DOMAIN,
    FAMILY_HUB,
    FAMILY_TRV,
    HUB_MODELS,
)


class HiveHomeLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Minimal config flow - connection details only.

    All device configuration is done after install via the Configure button.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Present a menu: add a Hub or TRV entry."""
        return self.async_show_menu(
            step_id="user",
            menu_options={
                "hub": "Heating Hub (SLR1 / SLR2 / OTR1)",
                "trv": "Radiator Valves (UK7004240 / TRV001)",
            },
        )

    async def async_step_hub(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Hub setup - model only. MQTT topic added via Configure afterward."""
        errors: dict[str, str] = {}

        if user_input is not None:
            model = user_input[CONF_MODEL]
            await self.async_set_unique_id(f"hub_{model}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Hive Hub ({model})",
                data={
                    CONF_DEVICE_FAMILY: FAMILY_HUB,
                    CONF_MODEL: model,
                    CONF_MQTT_TOPIC: "",
                    CONF_SHOW_HEAT_SCHEDULE_MODE: False,
                    CONF_SHOW_WATER_SCHEDULE_MODE: False,
                },
            )

        return self.async_show_form(
            step_id="hub",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=HUB_MODELS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="model",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_trv(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """TRV setup - Z2M base topic only. TRVs auto-discover after install."""
        errors: dict[str, str] = {}

        if user_input is not None:
            base = user_input[CONF_Z2M_BASE_TOPIC].strip().rstrip("/")
            await self.async_set_unique_id(f"trv_{base.replace('/', '_')}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Hive TRVs",
                data={
                    CONF_DEVICE_FAMILY: FAMILY_TRV,
                    CONF_Z2M_BASE_TOPIC: base,
                    CONF_BOILER_ENTITY: None,
                    CONF_PERSON_ENTITIES: [],
                },
            )

        return self.async_show_form(
            step_id="trv",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_Z2M_BASE_TOPIC, default="zigbee2mqtt"
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(placeholder="zigbee2mqtt")
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> "HiveHomeLocalOptionsFlow":
        """Return the options flow."""
        return HiveHomeLocalOptionsFlow(config_entry)


class HiveHomeLocalOptionsFlow(OptionsFlow):
    """Options flow - full device configuration, available any time after install."""

    def __init__(self, config_entry) -> None:
        """Initialise."""
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Route to hub or TRV options."""
        family = self._entry.data.get(CONF_DEVICE_FAMILY, FAMILY_HUB)
        if family == FAMILY_TRV:
            return await self.async_step_trv_options(user_input)
        return await self.async_step_hub_options(user_input)

    async def async_step_hub_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Hub configuration: MQTT topic, model, schedule toggles."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self._entry.options
        data = self._entry.data

        return self.async_show_form(
            step_id="hub_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MQTT_TOPIC,
                        description={"suggested_value": opts.get(CONF_MQTT_TOPIC, data.get(CONF_MQTT_TOPIC, ""))},
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            placeholder="zigbee2mqtt/Hive Hub"
                        )
                    ),
                    vol.Required(
                        CONF_MODEL,
                        default=opts.get(CONF_MODEL, data.get(CONF_MODEL, "SLR2")),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=HUB_MODELS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="model",
                        )
                    ),
                    vol.Optional(
                        CONF_SHOW_HEAT_SCHEDULE_MODE,
                        default=opts.get(
                            CONF_SHOW_HEAT_SCHEDULE_MODE,
                            data.get(CONF_SHOW_HEAT_SCHEDULE_MODE, False),
                        ),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_SHOW_WATER_SCHEDULE_MODE,
                        default=opts.get(
                            CONF_SHOW_WATER_SCHEDULE_MODE,
                            data.get(CONF_SHOW_WATER_SCHEDULE_MODE, False),
                        ),
                    ): selector.BooleanSelector(),
                }
            ),
        )

    async def async_step_trv_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """TRV configuration: boiler entity and geofencing persons."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_BOILER_ENTITY: user_input.get(CONF_BOILER_ENTITY) or None,
                    CONF_PERSON_ENTITIES: user_input.get(CONF_PERSON_ENTITIES) or [],
                },
            )

        opts = self._entry.options
        data = self._entry.data

        return self.async_show_form(
            step_id="trv_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_BOILER_ENTITY,
                        description={"suggested_value": opts.get(CONF_BOILER_ENTITY, data.get(CONF_BOILER_ENTITY))},
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["climate", "switch", "input_boolean"]
                        )
                    ),
                    vol.Optional(
                        CONF_PERSON_ENTITIES,
                        description={"suggested_value": opts.get(CONF_PERSON_ENTITIES, data.get(CONF_PERSON_ENTITIES, []))},
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="person", multiple=True
                        )
                    ),
                }
            ),
        )
