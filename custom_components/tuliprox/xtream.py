"""Xtream API client for Tuliprox account and content information."""

import asyncio
from datetime import datetime, timezone
from typing import Any

import aiohttp


class XtreamError(Exception):
    """Base exception for Xtream API errors."""


class XtreamAuthError(XtreamError):
    """Authentication error for Xtream API."""


class XtreamClient:
    """Client for Xtream Codes API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the Xtream client."""
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password

    async def _request(self, action: str | None = None) -> dict[str, Any]:
        """Make a request to the Xtream API."""
        params = {"username": self._username, "password": self._password}
        if action:
            params["action"] = action

        url = f"{self._base_url}/player_api.php"
        try:
            async with self._session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 403:
                    raise XtreamAuthError("Xtream authentication failed")
                if response.status != 200:
                    raise XtreamError(f"Xtream API returned {response.status}")
                
                data = await response.json()
                
                # Check for authentication error in response
                if isinstance(data, dict) and "user_info" in data:
                    user_info = data["user_info"]
                    if user_info.get("auth") != 1:
                        raise XtreamAuthError("Xtream authentication failed")
                
                return data
        except aiohttp.ClientError as err:
            raise XtreamError(f"Xtream API request failed: {err}") from err

    async def async_get_user_info(self) -> dict[str, Any]:
        """Get user account information."""
        data = await self._request()
        return data.get("user_info", {})

    async def async_get_server_info(self) -> dict[str, Any]:
        """Get server information."""
        data = await self._request()
        return data.get("server_info", {})

    async def async_get_live_streams(self) -> list[dict[str, Any]]:
        """Get list of live streams."""
        return await self._request("get_live_streams")

    async def async_get_vod_streams(self) -> list[dict[str, Any]]:
        """Get list of VOD streams."""
        return await self._request("get_vod_streams")

    async def async_get_series(self) -> list[dict[str, Any]]:
        """Get list of series."""
        return await self._request("get_series")

    async def async_get_full_info(self) -> dict[str, Any]:
        """Get complete account and content information."""
        # Get user and server info
        base_data = await self._request()
        
        # Get content counts in parallel
        live_streams, vod_streams, series = await asyncio.gather(
            self.async_get_live_streams(),
            self.async_get_vod_streams(),
            self.async_get_series(),
            return_exceptions=True,
        )
        
        # Handle exceptions
        if isinstance(live_streams, Exception):
            live_streams = []
        if isinstance(vod_streams, Exception):
            vod_streams = []
        if isinstance(series, Exception):
            series = []
        
        user_info = base_data.get("user_info", {})
        server_info = base_data.get("server_info", {})
        
        # Calculate expiry date
        exp_date = None
        if exp_timestamp := user_info.get("exp_date"):
            try:
                exp_date = datetime.fromtimestamp(
                    int(exp_timestamp), tz=timezone.utc
                ).isoformat()
            except (ValueError, TypeError, OSError):
                pass
        
        return {
            "username": user_info.get("username"),
            "status": user_info.get("status"),
            "is_trial": user_info.get("is_trial") == "1",
            "exp_date": exp_date,
            "max_connections": int(user_info.get("max_connections", 0) or 0),
            "active_connections": int(user_info.get("active_cons", 0) or 0),
            "created_at": user_info.get("created_at"),
            "live_streams_count": len(live_streams),
            "vod_streams_count": len(vod_streams),
            "series_count": len(series),
            "server_url": server_info.get("url"),
            "server_port": server_info.get("port"),
            "server_timezone": server_info.get("timezone"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
