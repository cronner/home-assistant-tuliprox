"""Tuliprox integration setup."""

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import TuliproxClient
from .const import DOMAIN, STATIC_URL
from .coordinator import TuliproxConfigEntry, TuliproxCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the single public JS resource once per Home Assistant instance."""
    state = hass.data.setdefault(DOMAIN, {})
    if not state.get("static_registered"):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    STATIC_URL,
                    str(Path(__file__).parent / "frontend" / "tuliprox-status-card.js"),
                    False,
                )
            ]
        )
        state["static_registered"] = True
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TuliproxConfigEntry) -> bool:
    """Validate initial connectivity and set up entities."""
    client = TuliproxClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = TuliproxCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TuliproxConfigEntry) -> bool:
    """Unload entities; HA owns the session and coordinator lifecycle."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
