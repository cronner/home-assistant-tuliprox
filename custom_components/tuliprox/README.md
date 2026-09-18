# Tuliprox for Home Assistant

Local polling custom integration, targeting Home Assistant 2026.9.2. Backend
only. This is not an official Home Assistant integration or a frontend card.

## Install and setup

The integration belongs in `custom_components/tuliprox/` under the Home
Assistant configuration directory. Back up the installation before deployment.
A full Home Assistant restart is required to discover new integration code;
no restart or entry creation is performed by installing these files.

After a separately approved restart, use **Settings > Devices & services >
Add integration > Tuliprox**. Supply the server's HTTP(S) base URL, username
and password. A reverse-proxy base path is allowed. Embedded URL credentials,
query strings and fragments are rejected. Prefer HTTPS; certificate validation
is enabled and cannot be disabled. HTTP sends the login over the local network
without encryption. Redirects are deliberately not followed.

The entry's **Reconfigure** action changes URL, username and password. Enter
the password again; stored passwords are never prefilled. All three connection
flows validate both API responses before saving. Authentication rejection
triggers Home Assistant's reauthentication flow and stops coordinator polling.
There is no documented immutable server/account ID, so none is invented; URL
changes preserve the existing entry and entity unique IDs. Duplicate normalized
URLs are rejected, but different aliases of the same server cannot be detected.

**Options** sets the interval (10-3600 seconds, default 30) and comma-separated
tracked usernames (default `rikke,thomas`, maximum 20). Matching is exact and
case-sensitive. Empty input disables user tracking. Changing options reloads
the entry. Removed users may leave unavailable entity-registry entries, which
can be deleted through the UI; no registry cleanup is performed automatically.

Home Assistant manages persistence of the login in its config entry. The JWT
exists only in client memory. Do not publish config-entry exports or backups
containing credentials. The integration never writes a status/token disk cache,
logs response bodies, or requests the API configuration endpoint.

## API and availability

Only these endpoints are used:

- `POST /auth/token`, JSON username/password, response object with `token`.
- Authenticated `GET /api/v1/status`, response object.
- Authenticated `GET /api/v1/streams`, response list.

Requests use HA's shared aiohttp session. Each request has a 10-second timeout
and at most one retry for transport errors, HTTP 429 or HTTP 5xx, with a
0.5-second delay. An entire poll has a 45-second deadline. HTTP 401 permits
at most one JWT refresh per poll, with one replay of the rejected GET; a
repeated 401 or any 403 is an authentication failure. Responses are limited to
2 MiB each and 2000 streams. Invalid JSON, unexpected top-level schemas or
oversized responses fail the complete update rather than publish partial data.

Failed updates make all entities unavailable. The server's public attributes
are cleared to `null`, not stale `ok` data. Recovery occurs on a successful poll,
or after reauthentication for an auth failure. Missing/invalid fields are
`None`/unknown, never synthesized as zero. A valid empty stream list has a
known stream count of zero. A reported status other than `ok` is preserved,
not silently converted to a healthy state.

## Sensors

Device name: `Tuliprox`. Sensor names are intentionally Danish regardless of
UI language. Suggested IDs below are not guaranteed by Home Assistant:

| Suggested suffix after `sensor.tuliprox_` | Meaning |
| --- | --- |
| `status` | Reported status |
| `version` | Reported version |
| `aktive_brugere` | `active_users` |
| `aktive_forbindelser` | `active_user_connections` |
| `aktive_streams` | `stream_count`, the length of the verified `/api/v1/streams` list |
| `aktive_udbyderforbindelser` | `active_provider_connections` |
| `rikke_stream`, `thomas_stream` | Matching channel titles or `Ingen stream` |
| `server` | Version state plus the card attributes below |
| `oppetid` | Nonnegative finite `uptime_secs`, seconds |
| `cache` | Sanitized display string, numeric value, or `Aktiv`/`Inaktiv` for a boolean |
| `byggetid`, `servertid` | Aware ISO or observed Tuliprox timestamps, normalized to UTC |

All sensors are created consistently, even when an optional field is absent.
Cache strings such as `281.86 MB / 10.00 GB` pass through the same `safe_text`
privacy filter as other display strings. Arbitrary cache objects/lists are
unknown and never exposed. In addition to timezone-aware ISO timestamps, the
observed formats `2026-09-15 11:44:15 UTC` and `2026-09-19 00:46:21 +02:00`
are supported. These become `2026-09-15T11:44:15+00:00` and
`2026-09-18T22:46:21+00:00`, respectively. Naive timestamps, other timezone
abbreviations and numeric epochs remain unknown; no timezone or epoch units
are guessed. Nonnegative numeric counts are accepted; strings and booleans
are not numeric counts.

The status endpoint's observed `active_user_streams` value is a list, not a
number, and is not used for the Aktive streams sensor. The sensor uses the
verified stream endpoint count, including zero for a valid empty list. Its
existing `active_user_streams` unique-ID key is retained to avoid replacing
the entity. `updated_at` and the card attribute contract remain unchanged.

Tracked sensors join distinct matching titles, truncated to HA's 255-character
state limit. A matching stream without a usable title is unknown. If any stream
has an unrecognized username and no match is found, the tracked sensor is
unknown rather than incorrectly reporting inactivity. Tracking does not query
an account directory, establish account existence, identify a person, or infer
subscription, entitlement, content category or viewing history.

## Card contract and static file

The server sensor state is the version. Its integration attributes are exactly:

`status`, `version`, `uptime_secs`, `cache`, `active_users`,
`active_user_connections`, `stream_count`, `streams`, `updated_at`.

`updated_at` is the timezone-aware UTC time of the last complete successful
fetch. Home Assistant also supplies standard attributes such as `friendly_name`.
Every stream is projected to this shape only:

```json
{"username": "rikke", "channel": {"title": "Example channel"}}
```

Missing fields are `null`. No raw stream objects, URLs, network addresses,
tokens, connection details or provider fields are copied. Display text with
obvious URL, IP or credential patterns or the known password/current token is
suppressed. This is schema-based
minimization, not a guarantee that an upstream server cannot put arbitrary
sensitive text inside an allowed display field. Usernames and titles themselves
may be personal data and can be recorded by Home Assistant. The frontend must
render these as text, never unsanitized HTML, and honor the entity's unavailable
state instead of treating cleared attributes as zero activity.

The backend registers the exact public static route
`/tuliprox/static/tuliprox-status-card.js` using `async_register_static_paths`.
Only `frontend/tuliprox-status-card.js` is served, not the integration directory.
Registration is per HA instance and survives entry reload/unload; it does not
depend on a module-global flag. The JavaScript file is a separate frontend
deliverable and is not included here. Until it exists the route returns 404.

Once that frontend is supplied, add the URL above as a **JavaScript module**
dashboard resource and configure its documented card type with the actual
server sensor entity ID. Card type and configuration are defined by that
frontend, not invented by this backend. No resource or dashboard is created
automatically.

## Migration

Existing REST/template sensors and dashboards are not modified. Record their
entity IDs and consumers before migration. After setup, compare the new live
values and unavailable behavior, then use Home Assistant's UI or approved
registry tooling to resolve ID collisions and update consumers. Disable/remove
old YAML only after explicit approval and validation. Keeping old entities can
cause HA to append `_2` to the suggested IDs.

Entity unique IDs are `<entry_id>_<key>`; tracked keys are
`user_<exact_username>_stream`. Reconfigure/reauth preserve them. Deleting and
recreating the entry changes its ID; no automatic identity migration is claimed.

## Verification

Standalone API tests live in `/data/tuliprox-tests/`. They load `api.py` directly
and use an ephemeral loopback aiohttp server, never a real Tuliprox endpoint.
Run `python -m unittest discover -s /data/tuliprox-tests -v` in an environment
with aiohttp. Python 3.13+ is needed to syntax-check all backend files.

`fixtures/observed_status_fields.json` contains the supplied observed cache,
build/server timestamps and empty stream lists, without inventing values for
other fields. Regression tests cover their projection through the mock HTTP
server, unsafe cache rejection, and the sensor property's stream-count mapping.

These tests do not validate Home Assistant config flows, entity registry,
coordinator scheduling, translations rendering or static serving at runtime.
Those need a matching HA test environment and a separately approved live setup.
The nonempty stream schema remains provisional until verified against real,
redacted API evidence.
