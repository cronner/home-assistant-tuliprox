"""Danish-named Tuliprox sensors and the card's sanitized server contract."""

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_TRACKED_USERS, DEFAULT_TRACKED_USERS, DOMAIN
from .coordinator import TuliproxConfigEntry, TuliproxCoordinator

PARALLEL_UPDATES = 0
DESCRIPTIONS = (
    SensorEntityDescription(key="status", name="Status", icon="mdi:server-network"),
    SensorEntityDescription(key="version", name="Version", icon="mdi:tag-outline"),
    SensorEntityDescription(
        key="active_users", name="Aktive brugere", icon="mdi:account-group"
    ),
    SensorEntityDescription(
        key="active_user_connections",
        name="Aktive forbindelser",
        icon="mdi:lan-connect",
    ),
    SensorEntityDescription(
        key="active_user_streams", name="Aktive streams", icon="mdi:play-network"
    ),
    SensorEntityDescription(
        key="active_provider_connections",
        name="Aktive udbyderforbindelser",
        icon="mdi:lan-connect",
    ),
    SensorEntityDescription(key="server", name="Server", icon="mdi:server"),
    SensorEntityDescription(
        key="uptime_secs",
        name="Oppetid",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
    SensorEntityDescription(key="cache", name="Cache", icon="mdi:memory"),
    SensorEntityDescription(
        key="build_time", name="Byggetid", device_class=SensorDeviceClass.TIMESTAMP
    ),
    SensorEntityDescription(
        key="server_time", name="Servertid", device_class=SensorDeviceClass.TIMESTAMP
    ),
)
SERVER_ATTRIBUTES = (
    "status",
    "version",
    "uptime_secs",
    "cache",
    "active_users",
    "active_user_connections",
    "stream_count",
    "streams",
    "updated_at",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuliproxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities = [TuliproxSensor(entry, description) for description in DESCRIPTIONS]
    for username in entry.options.get(CONF_TRACKED_USERS, DEFAULT_TRACKED_USERS):
        entities.append(
            TuliproxSensor(
                entry,
                SensorEntityDescription(
                    key=f"user_{username}_stream",
                    name=f"{username.capitalize()} stream",
                    icon="mdi:television-play",
                ),
                username,
            )
        )
    async_add_entities(entities)


class TuliproxSensor(CoordinatorEntity[TuliproxCoordinator], SensorEntity):
    """A sensor with stable entry-scoped identity and no stale attributes."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: TuliproxConfigEntry,
        description: SensorEntityDescription,
        username: str | None = None,
    ) -> None:
        super().__init__(entry.runtime_data)
        self.entity_description = description
        self._username = username
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Tuliprox",
            manufacturer="Tuliprox",
        )

    @property
    def native_value(self) -> Any:
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            return None
        data = self.coordinator.data
        if self._username is not None:
            streams = data["streams"]
            matches = [item for item in streams if item["username"] == self._username]
            if matches:
                titles = [item["channel"]["title"] for item in matches]
                if any(title is None for title in titles):
                    return None
                return ", ".join(dict.fromkeys(titles))[:255]
            # An unrecognized username field must not imply the user is idle.
            return (
                None
                if any(item["username"] is None for item in streams)
                else "Ingen stream"
            )
        key = self.entity_description.key
        # Preserve the entity's identity, but count the verified stream endpoint.
        if key == "active_user_streams":
            return data.get("stream_count")
        value = data.get("version" if key == "server" else key)
        if key == "cache" and isinstance(value, bool):
            return "Aktiv" if value else "Inaktiv"
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "server":
            return None
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            return {key: None for key in SERVER_ATTRIBUTES}
        return {key: self.coordinator.data.get(key) for key in SERVER_ATTRIBUTES}
