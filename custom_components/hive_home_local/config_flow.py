"""Config flow for Hive Home Local — supports Hub (SLR/OTR) and TRV devices."""

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
    """Config flow for Hive Home Local."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask which device family to set up."""
        return self.async_show_menu(
            step_id="user",
            menu_options={
                "hub": "Heating Hub (SLR1 / SLR2 / OTR1)",
                "trv": "Radiator Valve (UK7004240 / TRV001)",
            },
        )

    async def async_step_hub(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a Hive hub device (SLR1, SLR2, OTR1)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"hub_{user_input[CONF_MQTT_TOPIC].replace('/', '_')}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Hive Hub ({user_input[CONF_MODEL]})",
                data={
                    CONF_DEVICE_FAMILY: FAMILY_HUB,
                    CONF_MQTT_TOPIC: user_input[CONF_MQTT_TOPIC],
                    CONF_MODEL: user_input[CONF_MODEL],
                    CONF_SHOW_HEAT_SCHEDULE_MODE: user_input.get(CONF_SHOW_HEAT_SCHEDULE_MODE, False),
                    CONF_SHOW_WATER_SCHEDULE_MODE: user_input.get(CONF_SHOW_WATER_SCHEDULE_MODE, False),
                },
            )

        return self.async_show_form(
            step_id="hub",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MQTT_TOPIC): selector.TextSelector(
                        selector.TextSelectorConfig(placeholder="zigbee2mqtt/Hive Hub")
                    ),
                    vol.Required(CONF_MODEL): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=HUB_MODELS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_SHOW_HEAT_SCHEDULE_MODE, default=False): selector.BooleanSelector(),
                    vol.Optional(CONF_SHOW_WATER_SCHEDULE_MODE, default=False): selector.BooleanSelector(),
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    async def async_step_trv(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up TRV auto-discovery via Zigbee2MQTT."""
        errors: dict[str, str] = {}

        if user_input is not None:
            base_topic = user_input[CONF_Z2M_BASE_TOPIC].rstrip("/")
            await self.async_set_unique_id(f"trv_{base_topic.replace('/', '_')}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Hive TRVs (via Zigbee2MQTT)",
                data={
                    CONF_DEVICE_FAMILY: FAMILY_TRV,
                    CONF_Z2M_BASE_TOPIC: base_topic,
                    CONF_BOILER_ENTITY: user_input.get(CONF_BOILER_ENTITY, ""),
                    CONF_PERSON_ENTITIES: user_input.get(CONF_PERSON_ENTITIES, []),
                },
            )

        return self.async_show_form(
            step_id="trv",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_Z2M_BASE_TOPIC, default="zigbee2mqtt"): selector.TextSelector(
                        selector.TextSelectorConfig(placeholder="zigbee2mqtt")
                    ),
                    vol.Optional(CONF_BOILER_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["climate", "switch", "input_boolean"]
                        )
                    ),
                    vol.Optional(CONF_PERSON_ENTITIES): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="person", multiple=True)
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return HiveHomeLocalOptionsFlow(config_entry)


class HiveHomeLocalOptionsFlow(OptionsFlow):
    """Options flow for reconfiguring after initial setup."""

    def __init__(self, config_entry) -> None:
        """Initialise."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Route to the correct options step based on device family."""
        family = self._config_entry.data.get(CONF_DEVICE_FAMILY, FAMILY_HUB)
        if family == FAMILY_TRV:
            return await self.async_step_trv_options(user_input)
        return await self.async_step_hub_options(user_input)

    async def async_step_hub_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Hub options: update MQTT topic, model, schedule display toggles."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.data
        return self.async_show_form(
            step_id="hub_options",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MQTT_TOPIC, default=current.get(CONF_MQTT_TOPIC, "")): selector.TextSelector(),
                    vol.Required(CONF_MODEL, default=current.get(CONF_MODEL, "SLR2")): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=HUB_MODELS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_SHOW_HEAT_SCHEDULE_MODE, default=current.get(CONF_SHOW_HEAT_SCHEDULE_MODE, False)): selector.BooleanSelector(),
                    vol.Optional(CONF_SHOW_WATER_SCHEDULE_MODE, default=current.get(CONF_SHOW_WATER_SCHEDULE_MODE, False)): selector.BooleanSelector(),
                }
            ),
        )

    async def async_step_trv_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """TRV options: update boiler entity and person entities."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.data
        return self.async_show_form(
            step_id="trv_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_BOILER_ENTITY,
                        default=current.get(CONF_BOILER_ENTITY, ""),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["climate", "switch", "input_boolean"]
                        )
                    ),
                    vol.Optional(
                        CONF_PERSON_ENTITIES,
                        default=current.get(CONF_PERSON_ENTITIES, []),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="person", multiple=True)
                    ),
                }
            ),
        )
