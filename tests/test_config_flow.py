"""Setting Memory Card up from the app's discovery message."""

from homeassistant.config_entries import SOURCE_HASSIO, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.memory_card.const import CONF_SLUG, DOMAIN

from .conftest import TOKEN, UUID, FakeApp


def discovery(port: int, token: str = TOKEN, **config: object) -> HassioServiceInfo:
    return HassioServiceInfo(
        config={
            "host": "127.0.0.1",
            "port": port,
            "token": token,
            "addon": "Memory Card",
            **config,
        },
        name="Memory Card",
        slug="local_memory_card",
        uuid=UUID,
    )


async def test_the_app_announces_itself_and_one_click_adds_it(
    hass: HomeAssistant, fake_app: FakeApp
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=discovery(fake_app.port)
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"addon": "Memory Card"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Memory Card"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: fake_app.port,
        CONF_TOKEN: TOKEN,
        CONF_SLUG: "local_memory_card",
    }
    # Home Assistant removes the entry when the app withdraws this message.
    entry = result["result"]
    assert entry.unique_id == UUID
    assert entry.source == SOURCE_HASSIO


async def test_a_new_announcement_updates_the_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_app: FakeApp
) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_HASSIO},
        data=discovery(fake_app.port, token="f" * 64, host="local-memory-card"),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_TOKEN] == "f" * 64
    assert config_entry.data[CONF_HOST] == "local-memory-card"


@pytest.mark.parametrize(
    "config",
    [
        {"token": None},
        {"token": ""},
        {"token": "g" * 64},
        {"token": "a" * 63},
        {"token": "a" * 64 + "\r\nX-Evil: 1"},
        {"port": True},
        {"port": 0},
        {"port": 70000},
        {"port": "8100"},
        {"host": ""},
        {"host": "bad host/name"},
    ],
)
async def test_an_announcement_with_unusable_details_is_refused(
    hass: HomeAssistant, config: dict[str, object]
) -> None:
    info = discovery(8100)
    info.config.update(config)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery"


async def test_adding_it_by_hand_points_at_the_app_option(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_only"
