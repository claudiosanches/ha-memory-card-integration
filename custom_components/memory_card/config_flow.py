"""Set up Memory Card when the app announces itself."""

import re
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from yarl import URL

from .const import CONF_SLUG, DOMAIN

# The app's token: 32 random bytes as hex.
TOKEN = re.compile(r"[0-9a-f]{64}")


def _entry_data(discovery: HassioServiceInfo) -> dict[str, Any]:
    return {
        CONF_HOST: discovery.config[CONF_HOST],
        CONF_PORT: discovery.config[CONF_PORT],
        CONF_TOKEN: discovery.config[CONF_TOKEN],
        CONF_SLUG: discovery.slug,
    }


def _valid(config: dict[str, Any]) -> bool:
    """Whether the announcement holds an address the client can use and the app's token."""
    host, port, token = config.get(CONF_HOST), config.get(CONF_PORT), config.get(CONF_TOKEN)
    if not (isinstance(host, str) and host and isinstance(token, str) and TOKEN.fullmatch(token)):
        return False
    # bool is an int too.
    if type(port) is not int or not 1 <= port <= 65535:
        return False
    try:
        URL.build(scheme="http", host=host, port=port)
    except ValueError:
        return False
    return True


class MemoryCardConfigFlow(ConfigFlow, domain=DOMAIN):
    """Only the app's Supervisor discovery sets Memory Card up."""

    VERSION = 1

    _discovery: HassioServiceInfo

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        """Take the app's announcement; an existing entry gets the new details."""
        if not _valid(discovery_info.config):
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
