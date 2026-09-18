"""Bounded standalone tests. Only generated credentials and loopback requests."""

import asyncio
import importlib.util
import json
import secrets
import unittest
from collections import Counter
from pathlib import Path

import aiohttp
from aiohttp import web

SOURCE = Path(__file__).parent.parent / "custom_components" / "tuliprox" / "api.py"
spec = importlib.util.spec_from_file_location("tuliprox_api", SOURCE)
assert spec is not None and spec.loader is not None
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.username = secrets.token_hex(8)
        self.password = secrets.token_urlsafe(24)
        self.token = secrets.token_urlsafe(32)
        self.counts = Counter()
        self.responses = {}
        self.status = {"status": "ok", "version": "1.2.3", "active_users": 0}
        self.streams = []
        self.login_valid = True
        app = web.Application()
        app.router.add_route("*", "/{path:.*}", self.handler)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        port = self.runner.addresses[0][1]
        self.url = f"http://127.0.0.1:{port}"
        self.session = aiohttp.ClientSession()
        self.client = api.TuliproxClient(
            self.session,
            self.url,
            self.username,
            self.password,
            request_timeout=0.1,
            retry_delay=0,
        )

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()

    async def handler(self, request):
        path = request.path
        self.counts[path] += 1
        if self.responses.get(path):
            response = self.responses[path].pop(0)
            if response == "timeout":
                await asyncio.sleep(0.25)
                return web.Response(status=503)
            if isinstance(response, int):
                return web.Response(status=response, text=self.password)
            return response
        if path == "/auth/token":
            payload = await request.json()
            self.login_valid &= payload == {
                "username": self.username,
                "password": self.password,
            }
            return web.json_response({"token": self.token})
        if request.headers.get("Authorization") != f"Bearer {self.token}":
            return web.Response(status=401)
        if path == "/api/v1/status":
            return web.json_response(self.status)
        if path == "/api/v1/streams":
            return web.json_response(self.streams)
        return web.Response(status=404)

    async def test_success_and_token_reuse(self):
        result = await self.client.async_snapshot()
        await self.client.async_snapshot()
        self.assertTrue(self.login_valid)
        self.assertEqual(self.counts["/auth/token"], 1)
        self.assertEqual(result["stream_count"], 0)
        self.assertEqual(result["active_users"], 0)
        self.assertIsNone(result["active_user_connections"])

    async def test_observed_status_fields(self):
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/observed_status_fields.json").read_text()
        )
        self.status = fixture["status"]
        self.streams = fixture["streams"]
        result = await self.client.async_snapshot()
        self.assertEqual(result["cache"], "281.86 MB / 10.00 GB")
        self.assertEqual(result["build_time"].isoformat(), "2026-09-15T11:44:15+00:00")
        self.assertEqual(result["server_time"].isoformat(), "2026-09-18T22:46:21+00:00")
        self.assertEqual(result["stream_count"], 0)
        self.assertNotIn("active_user_streams", result)
        self.assertIsNotNone(api.timestamp(result["updated_at"]))
        # Synthetic nonempty endpoint confirms the status list is not the count.
        self.streams = [{"username": "rikke", "channel": {"title": "News"}}]
        self.assertEqual((await self.client.async_snapshot())["stream_count"], 1)

    async def test_refresh_401_once(self):
        self.responses["/api/v1/status"] = [401]
        result = await self.client.async_snapshot()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(self.counts["/auth/token"], 2)

    async def test_repeated_401_is_auth_failure(self):
        self.responses["/api/v1/status"] = [401, 401]
        with self.assertRaises(api.TuliproxAuthError):
            await self.client.async_snapshot()
        self.assertEqual(self.counts["/auth/token"], 2)
        self.assertEqual(self.counts["/api/v1/status"], 2)

    async def test_refresh_budget_shared_between_endpoints(self):
        self.responses["/api/v1/status"] = [401]
        self.responses["/api/v1/streams"] = [401]
        with self.assertRaises(api.TuliproxAuthError):
            await self.client.async_snapshot()
        self.assertEqual(self.counts["/auth/token"], 2)

    async def test_login_rejected_without_leaking_body(self):
        self.responses["/auth/token"] = [401]
        with self.assertRaises(api.TuliproxAuthError) as caught:
            await self.client.async_snapshot()
        self.assertNotIn(self.password, str(caught.exception))
        self.assertEqual(self.counts["/auth/token"], 1)

    async def test_forbidden_does_not_refresh(self):
        self.responses["/api/v1/streams"] = [403]
        with self.assertRaises(api.TuliproxAuthError):
            await self.client.async_snapshot()
        self.assertEqual(self.counts["/auth/token"], 1)

    async def test_transient_retry_success(self):
        for code in (429, 500, 503):
            self.responses["/api/v1/status"] = [code]
            self.assertEqual((await self.client.async_snapshot())["status"], "ok")

    async def test_retry_exhaustion_is_bounded(self):
        self.responses["/api/v1/status"] = [503, 503, 503]
        with self.assertRaises(api.TuliproxError) as caught:
            await self.client.async_snapshot()
        self.assertEqual(self.counts["/api/v1/status"], 2)
        self.assertNotIn(self.password, str(caught.exception))

    async def test_timeout_is_bounded(self):
        self.responses["/api/v1/status"] = ["timeout", "timeout"]
        with self.assertRaises(api.TuliproxError):
            await asyncio.wait_for(self.client.async_snapshot(), 2)
        self.assertEqual(self.counts["/api/v1/status"], 2)

    async def test_redirect_not_followed(self):
        self.responses["/api/v1/status"] = [
            web.Response(status=302, headers={"Location": "/forbidden"})
        ]
        with self.assertRaises(api.TuliproxError):
            await self.client.async_snapshot()
        self.assertEqual(self.counts["/forbidden"], 0)

    async def test_bad_json(self):
        self.responses["/api/v1/status"] = [web.Response(text="not JSON")]
        with self.assertRaises(api.TuliproxError):
            await self.client.async_snapshot()

    async def test_missing_token(self):
        self.responses["/auth/token"] = [web.json_response({})]
        with self.assertRaises(api.TuliproxError):
            await self.client.async_snapshot()

    async def test_oversized_response(self):
        self.responses["/api/v1/status"] = [
            web.Response(body=b" " * (api.MAX_RESPONSE_BYTES + 1))
        ]
        with self.assertRaises(api.TuliproxError):
            await self.client.async_snapshot()

    async def test_failed_second_endpoint_never_returns_partial_snapshot(self):
        await self.client.async_snapshot()
        self.responses["/api/v1/streams"] = [500, 500]
        with self.assertRaises(api.TuliproxError):
            await self.client.async_snapshot()

    async def test_whitelist_projection(self):
        self.streams = [
            {
                "username": "rikke",
                "password": self.password,
                "url": self.url,
                "ip": "127.0.0.1",
                "channel": {"title": "News", "url": self.url},
            }
        ]
        self.status["cache"] = {"password": self.password}
        data = await self.client.async_snapshot()
        self.assertEqual(
            data["streams"], [{"username": "rikke", "channel": {"title": "News"}}]
        )
        self.assertIsNone(data["cache"])
        self.assertNotIn(self.password, json.dumps(data))
        self.assertNotIn(self.url, json.dumps(data))

    async def test_echoed_credentials_in_display_fields(self):
        self.streams = [{"username": self.password, "channel": {"title": self.token}}]
        self.status["version"] = self.password
        result = await self.client.async_snapshot()
        self.assertIsNone(result["version"])
        self.assertEqual(
            result["streams"], [{"username": None, "channel": {"title": None}}]
        )

    async def test_cancellation_propagates(self):
        self.responses["/auth/token"] = ["timeout"]
        task = asyncio.create_task(self.client.async_snapshot())
        await asyncio.sleep(0.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task


class ProjectionTests(unittest.TestCase):
    def test_missing_values_and_uncertain_stream_schema(self):
        data = api.project_snapshot({}, [{"user": "rikke", "channel": "News"}])
        self.assertIsNone(data["active_users"])
        self.assertIsNone(data["status"])
        self.assertEqual(
            data["streams"], [{"username": None, "channel": {"title": None}}]
        )

    def test_invalid_schema(self):
        for status, streams in (([], []), ({}, {}), ({}, [None]), ({}, [{}] * 2001)):
            with self.assertRaises(api.TuliproxError):
                api.project_snapshot(status, streams)

    def test_numbers(self):
        for value in (None, True, "0", -1, float("nan"), float("inf"), 10**400):
            self.assertIsNone(api.number(value))
        self.assertEqual(api.number(0), 0)

    def test_dates(self):
        self.assertIsNotNone(api.timestamp("2026-09-19T12:00:00Z"))
        self.assertIsNotNone(api.timestamp("2026-09-19T14:00:00+02:00"))
        for value in (
            0,
            "bad",
            "2026-09-19",
            "2026-09-19T12:00:00",
            "2026-09-19 12:00:00",
            "2026-09-19 12:00:00 CEST",
            "2026-02-30 12:00:00 UTC",
            "2026-09-19 12:00:00 +25:00",
        ):
            self.assertIsNone(api.timestamp(value))

    def test_cache_projection(self):
        for value in ("281.86 MB / 10.00 GB", 0, 128, True, False):
            self.assertEqual(api.project_snapshot({"cache": value}, [])["cache"], value)
        for value in (
            {"size": 128},
            [128],
            "https://example.invalid",
            "token=private",
            "",
            None,
        ):
            self.assertIsNone(api.project_snapshot({"cache": value}, [])["cache"])
        secret = secrets.token_urlsafe(24)
        self.assertIsNone(
            api.project_snapshot({"cache": secret}, [], (secret,))["cache"]
        )

    def test_sensitive_display_values(self):
        for value in (
            "https://example.invalid/private",
            "127.0.0.1",
            "::1",
            "token=private",
            "Bearer private",
        ):
            self.assertIsNone(api.safe_text(value))
        self.assertEqual(api.safe_text("DR 1"), "DR 1")

    def test_urls(self):
        self.assertEqual(
            api.normalize_url(" https://example.invalid/base/ "),
            "https://example.invalid/base",
        )
        for value in (
            "file:///tmp/a",
            "https://user@example.invalid",
            "https://example.invalid?token=x",
            "https://example.invalid/#fragment",
            "http://example.invalid:invalid",
        ):
            with self.assertRaisesRegex(ValueError, "^Invalid server URL$"):
                api.normalize_url(value)


if __name__ == "__main__":
    unittest.main()
