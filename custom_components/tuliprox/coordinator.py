"""Coordinate Tuliprox polling."""

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TuliproxAuthError, TuliproxClient, TuliproxError
from .const import CONF_INTERVAL, DEFAULT_INTERVAL, DOMAIN


class TuliproxCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Publish only complete, sanitized snapshots."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: TuliproxClient
    ) -> None:
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)
            ),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.async_snapshot()
        except TuliproxAuthError:
            raise ConfigEntryAuthFailed("Tuliprox authentication rejected") from None
        except TuliproxError:
            raise UpdateFailed("Unable to update Tuliprox") from None


type TuliproxConfigEntry = ConfigEntry[TuliproxCoordinator]
