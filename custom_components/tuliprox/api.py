"""Small asynchronous Tuliprox client, independent of Home Assistant."""

import asyncio
import ipaddress
import json
import math
import re
from datetime import datetime, timezone
from typing import Any

import aiohttp
from yarl import URL

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_STREAMS = 2000


class TuliproxError(Exception):
    """Communication or invalid response error with a safe message."""


class TuliproxAuthError(TuliproxError):
    """Authentication was rejected."""


def normalize_url(value: str) -> str:
    """Accept HTTP(S) base URLs, never embedded credentials or query strings."""
    try:
        url = URL(value.strip())
        if (
            url.scheme not in ("http", "https")
            or not url.host
            or url.user is not None
            or url.password is not None
            or url.query_string
            or url.fragment
        ):
            raise ValueError
        _ = url.port
        return str(url).rstrip("/")
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid server URL") from None


def safe_text(value: Any, sensitive_values: tuple[str, ...] = ()) -> str | None:
    """Project short display strings, rejecting obvious network/secret values."""
    if not isinstance(value, str) or not value.strip() or len(value) > 255:
        return None
    value = value.strip()
    if any(secret and secret in value for secret in sensitive_values):
        return None
    if any(ord(char) < 32 for char in value) or re.search(
        r"(?i)(://|www\.|bearer\s|password\s*[:=]|token\s*[:=]|"
        r"[?&](?:user(?:name)?|pass(?:word)?|token)=|"
        r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.|\b(?:\d{1,3}\.){3}\d{1,3}\b)",
        value,
    ):
        return None
    try:
        ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        return value
    return None


def number(value: Any) -> int | float | None:
    """Keep only finite nonnegative JSON numbers, never invent zero."""
    if type(value) is int and 0 <= value <= 2**63 - 1:
        return value
    if type(value) is float and 0 <= value <= 2**63 - 1 and math.isfinite(value):
        return value
    return None


def timestamp(value: Any) -> datetime | None:
    """Accept aware ISO timestamps and the observed Tuliprox time formats."""
    if not isinstance(value, str):
        return None
    if match := re.fullmatch(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (UTC|[+-]\d{2}:\d{2})", value
    ):
        value = match[1] + ("+00:00" if match[2] == "UTC" else match[2])
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        pass
    return None


def project_snapshot(
    status: Any,
    streams: Any,
    sensitive_values: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Discard all unapproved fields before data reaches HA or its recorder."""
    if not isinstance(status, dict) or not isinstance(streams, list):
        raise TuliproxError("Unexpected response schema")
    if len(streams) > MAX_STREAMS or any(
        not isinstance(item, dict) for item in streams
    ):
        raise TuliproxError("Unexpected stream response schema")
    projected = []
    for item in streams:
        channel = item.get("channel")
        projected.append(
            {
                "username": safe_text(item.get("username"), sensitive_values),
                "channel": {
                    "title": safe_text(channel.get("title"), sensitive_values)
                    if isinstance(channel, dict)
                    else None
                },
            }
        )
    # Cache display strings are known; arbitrary nested objects are not exposed.
    cache = status.get("cache")
    if isinstance(cache, str):
        cache = safe_text(cache, sensitive_values)
    elif not isinstance(cache, bool):
        cache = number(cache)
    data = {
        "status": safe_text(status.get("status"), sensitive_values),
        "version": safe_text(status.get("version"), sensitive_values),
        "cache": cache,
        "streams": projected,
        "stream_count": len(projected),
        "build_time": timestamp(status.get("build_time")),
        "server_time": timestamp(status.get("server_time")),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    for key in (
        "uptime_secs",
        "active_users",
        "active_user_connections",
        "active_provider_connections",
    ):
        data[key] = number(status.get(key))
    return data


class TuliproxClient:
    """Use an externally owned session; tokens live only in memory."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        username: str,
        password: str,
        *,
        request_timeout: float = 10,
        retry_delay: float = 0.5,
    ) -> None:
        self._session = session
        self._url = normalize_url(url)
        self._username = username
        self._password = password
        self._token: str | None = None
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)
        self._retry_delay = retry_delay
        self._lock = asyncio.Lock()

    async def _request(self, method: str, path: str, *, auth: bool = True) -> Any:
        """Retry transient failures once; never follow credential-bearing redirects."""
        for attempt in range(2):
            try:
                async with self._session.request(
                    method,
                    self._url + path,
                    headers={"Authorization": f"Bearer {self._token}"} if auth else {},
                    json=None
                    if auth
                    else {"username": self._username, "password": self._password},
                    timeout=self._timeout,
                    allow_redirects=False,
                ) as response:
                    if response.status in (401, 403):
                        if response.status == 401 and auth:
                            return _UNAUTHORIZED
                        raise TuliproxAuthError("Authentication rejected")
                    if response.status == 429 or response.status >= 500:
                        if attempt == 0:
                            await asyncio.sleep(self._retry_delay)
                            continue
                        raise TuliproxError("Server temporarily unavailable")
                    if response.status != 200:
                        raise TuliproxError("Unexpected HTTP response")
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise TuliproxError("Response exceeds size limit")
                    try:
                        return json.loads(body)
                    except (ValueError, UnicodeError, RecursionError):
                        raise TuliproxError("Invalid JSON response") from None
            except (aiohttp.ClientError, TimeoutError):
                if attempt == 1:
                    raise TuliproxError("Unable to communicate with server") from None
                await asyncio.sleep(self._retry_delay)
        raise TuliproxError("Unable to communicate with server")

    async def _authenticate(self) -> None:
        self._token = None
        payload = await self._request("POST", "/auth/token", auth=False)
        token = payload.get("token") if isinstance(payload, dict) else None
        if (
            not isinstance(token, str)
            or not token
            or len(token) > 16384
            or re.fullmatch(r"[A-Za-z0-9_.~+/=-]+", token) is None
        ):
            raise TuliproxError("Invalid authentication response")
        self._token = token

    async def async_snapshot(self) -> dict[str, Any]:
        """Fetch an atomic snapshot with one JWT refresh at most per poll."""
        async with self._lock:
            try:
                async with asyncio.timeout(45):
                    if self._token is None:
                        await self._authenticate()
                    refreshed = False
                    results = []
                    for path in ("/api/v1/status", "/api/v1/streams"):
                        payload = await self._request("GET", path)
                        if payload is _UNAUTHORIZED:
                            if refreshed:
                                self._token = None
                                raise TuliproxAuthError("Authentication rejected")
                            await self._authenticate()
                            refreshed = True
                            payload = await self._request("GET", path)
                            if payload is _UNAUTHORIZED:
                                self._token = None
                                raise TuliproxAuthError("Authentication rejected")
                        results.append(payload)
                    return project_snapshot(
                        *results, sensitive_values=(self._password, self._token or "")
                    )
            except TimeoutError:
                raise TuliproxError("Server update timed out") from None


_UNAUTHORIZED = object()
