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
from .xtream import XtreamClient, XtreamError


class TuliproxCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Publish only complete, sanitized snapshots."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: TuliproxClient,
        xtream_client: XtreamClient | None = None,
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
        self.xtream_client = xtream_client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.async_snapshot()
        except TuliproxAuthError:
            raise ConfigEntryAuthFailed("Tuliprox authentication rejected") from None
        except TuliproxError:
            raise UpdateFailed("Unable to update Tuliprox") from None
        
        # Fetch Xtream data if client is configured
        if self.xtream_client:
            try:
                xtream_data = await self.xtream_client.async_get_full_info()
                data["xtream"] = xtream_data
            except XtreamError as err:
                logging.getLogger(__name__).warning(
                    "Failed to fetch Xtream data: %s", err
                )
                data["xtream"] = None
        
        return data


type TuliproxConfigEntry = ConfigEntry[TuliproxCoordinator]
