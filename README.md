# Tuliprox Integration for Home Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A custom Home Assistant integration for monitoring Tuliprox IPTV panel servers.

## Features

- **Real-time server monitoring**: Status, version, uptime, cache usage
- **Active connection tracking**: Users, connections, and streams
- **Per-user stream monitoring**: Track what specific users are watching
- **Custom Lovelace card**: Beautiful status card with live updates
- **Configurable polling**: Adjust update frequency (10-3600 seconds)
- **Secure**: Credentials stored in Home Assistant config entry, never logged
- **Resilient**: Handles authentication failures, network issues, and server restarts

## Installation

### Manual Installation

1. Copy the `custom_components/tuliprox` directory to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to **Settings** → **Devices & Services** → **Add Integration**
4. Search for "Tuliprox" and configure:
   - **Server URL**: Your Tuliprox panel URL (e.g., `http://192.168.1.100:8901`)
   - **Username**: Your Tuliprox admin username
   - **Password**: Your Tuliprox admin password

### HACS Installation (Coming Soon)

This integration is not yet available in HACS. Use manual installation for now.

## Configuration

After installation, you can adjust settings via **Settings** → **Devices & Services** → **Tuliprox** → **Configure**:

- **Update interval**: How often to poll the server (default: 60 seconds)
- **Tracked users**: Comma-separated list of usernames to monitor (e.g., `rikke,thomas`)

## Sensors

The integration creates the following sensors:

### Server Information
- `sensor.tuliprox_status`: Server status (ok/error)
- `sensor.tuliprox_version`: Server version
- `sensor.tuliprox_server`: Combined server sensor with attributes
- `sensor.tuliprox_build_time`: Server build timestamp
- `sensor.tuliprox_server_time`: Current server time
- `sensor.tuliprox_uptime`: Server uptime (seconds)
- `sensor.tuliprox_cache`: Cache usage

### Connection Statistics
- `sensor.tuliprox_active_users`: Number of active users
- `sensor.tuliprox_active_connections`: Number of active connections
- `sensor.tuliprox_active_streams`: Number of active streams
- `sensor.tuliprox_active_provider_connections`: Provider connections

### User Tracking
For each tracked user (e.g., `rikke`, `thomas`):
- `sensor.tuliprox_rikke_stream`: What Rikke is currently watching
- `sensor.tuliprox_thomas_stream`: What Thomas is currently watching

## Custom Card

The integration includes a custom Lovelace card `custom:tuliprox-status-card` that displays:

- Server status with color-coded indicator
- Version and uptime information
- Cache usage
- Active users, connections, and streams
- List of currently active streams with usernames and channels

### Card Configuration

```yaml
type: custom:tuliprox-status-card
entity: sensor.tuliprox_server
title: Tuliprox Server
show_details: true
users:
  - rikke
  - thomas
```

**Options:**
- `entity`: The server sensor (required)
- `title`: Card title (optional)
- `show_details`: Show version/uptime/cache details (default: true)
- `users`: Filter streams to specific users (optional, shows all if omitted)

## API Requirements

The integration uses the Tuliprox WebUI API:
- `POST /auth/token` - Authentication
- `GET /api/v1/status` - Server status
- `GET /api/v1/streams` - Active streams

**Note**: The legacy Xtream `player_api.php` is not supported. Your Tuliprox server must have the WebUI API enabled.

## Testing

Run the test suite:

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run Python tests
python -m unittest discover tests

# Check JavaScript syntax
node --check custom_components/tuliprox/frontend/tuliprox-status-card.js
```

## Troubleshooting

### Integration fails to connect
- Verify the server URL is correct and accessible from Home Assistant
- Check that the username and password are correct
- Ensure the Tuliprox WebUI API is enabled on your server

### Sensors show "unknown" or "unavailable"
- Check the Home Assistant logs for connection errors
- Verify the server is online and responding
- Ensure the API endpoints are accessible

### Custom card not showing
- Verify the integration is loaded (check Settings → Devices & Services)
- Clear browser cache and reload the dashboard
- Check browser console for JavaScript errors

## Privacy & Security

- Credentials are stored securely in Home Assistant's config entry
- No data is sent to external services
- All communication is local (HTTP/HTTPS to your Tuliprox server)
- Sensitive values (passwords, tokens, IPs) are filtered from logs and attributes
- Stream data only exposes username and channel title (no URLs or credentials)

## Limitations

- **Konto/Content counts**: The current Tuliprox API does not expose account expiry or content library counts (channels/films/series) via the WebUI API. These sensors are not implemented.
- **Legacy Xtream API**: The integration does not support the deprecated `player_api.php` endpoints.

## Development

This integration was developed for Home Assistant 2026.9.2 and tested with Tuliprox 3.3.113.

### Project Structure
```
custom_components/tuliprox/
├── __init__.py          # Integration setup
├── api.py               # Tuliprox API client
├── config_flow.py       # Configuration UI
├── const.py             # Constants
├── coordinator.py       # Data update coordinator
├── sensor.py            # Sensor entities
├── manifest.json        # Integration metadata
├── strings.json         # UI strings
├── translations/        # Localization
└── frontend/
    └── tuliprox-status-card.js  # Custom Lovelace card
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## Support

For issues and questions:
- Open an issue on [GitHub](https://github.com/cronner/home-assistant-tuliprox/issues)
- Check the [Home Assistant Community Forum](https://community.home-assistant.io/)

## Credits

Developed by [@cronner](https://github.com/cronner)

Inspired by the Floppy integration pattern.
