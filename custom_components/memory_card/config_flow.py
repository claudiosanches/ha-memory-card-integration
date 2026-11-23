"""Set up Memory Card when the app announces itself."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import CONF_SLUG, DOMAIN


def _entry_data(discovery: HassioServiceInfo) -> dict[str, Any]:
    return {
        CONF_HOST: discovery.config[CONF_HOST],
        CONF_PORT: discovery.config[CONF_PORT],
        CONF_TOKEN: discovery.config[CONF_TOKEN],
        CONF_SLUG: discovery.slug,
    }


class MemoryCardConfigFlow(ConfigFlow, domain=DOMAIN):
    """Only the app's Supervisor discovery sets Memory Card up."""

    VERSION = 1

    _discovery: HassioServiceInfo

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        """Take the app's announcement; an existing entry gets the new details."""
        config = discovery_info.config
        if not (
            isinstance(config.get(CONF_HOST), str)
            and isinstance(config.get(CONF_PORT), int)
            and isinstance(config.get(CONF_TOKEN), str)
        ):
            return self.async_abort(reason="invalid_discovery")
        # Home Assistant removes the entry when the app withdraws this message.
        await self.async_set_unique_id(discovery_info.uuid)
        self._abort_if_unique_id_configured(updates=_entry_data(discovery_info))
        self._discovery = discovery_info
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask before adding it."""
        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(
                step_id="hassio_confirm",
                description_placeholders={"addon": self._discovery.name},
            )
        return self.async_create_entry(
            title=self._discovery.name, data=_entry_data(self._discovery)
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Point people at the app's option instead."""
        return self.async_abort(reason="discovery_only")
