"""Tuliprox integration setup."""

import os
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import TuliproxClient
from .const import CONF_XTREAM_PASSWORD, CONF_XTREAM_USERNAME, DOMAIN, STATIC_URL
from .coordinator import TuliproxConfigEntry, TuliproxCoordinator
from .xtream import XtreamClient

PLATFORMS = [Platform.SENSOR]

_CARD_SERVED = False


async def async_serve_card(hass: HomeAssistant) -> None:
    """Serve the bundled card JavaScript as a static HA route."""
    global _CARD_SERVED  # noqa: PLW0603
    if _CARD_SERVED:
        return
    card_file = os.path.join(os.path.dirname(__file__), "frontend", "tuliprox-status-card.js")
    if not os.path.isfile(card_file):
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, card_file, cache_headers=True)]
    )
    _CARD_SERVED = True


async def async_setup(_hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the integration from YAML (unused, config-flow only)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TuliproxConfigEntry) -> bool:
    """Validate initial connectivity and set up entities."""
    await async_serve_card(hass)
    
    client = TuliproxClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    
    # Initialize Xtream client if credentials are provided
    xtream_client = None
    xtream_username = entry.data.get(CONF_XTREAM_USERNAME)
    xtream_password = entry.data.get(CONF_XTREAM_PASSWORD)
    if xtream_username and xtream_password:
        xtream_client = XtreamClient(
            async_get_clientsession(hass),
            entry.data[CONF_URL],
            xtream_username,
            xtream_password,
        )
    
    coordinator = TuliproxCoordinator(hass, entry, client, xtream_client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TuliproxConfigEntry) -> bool:
    """Unload entities; HA owns the session and coordinator lifecycle."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
