"""User setup, reconfiguration, reauthentication and optional preferences."""

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    TuliproxAuthError,
    TuliproxClient,
    TuliproxError,
    normalize_url,
    safe_text,
)
from .const import (
    CONF_INTERVAL,
    CONF_TRACKED_USERS,
    CONF_XTREAM_PASSWORD,
    CONF_XTREAM_USERNAME,
    DEFAULT_INTERVAL,
    DEFAULT_TRACKED_USERS,
    DOMAIN,
)


class TuliproxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure a server without claiming a URL is an immutable device ID."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "TuliproxOptionsFlow":
        return TuliproxOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_credentials("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_credentials(
            "reconfigure", user_input, self._get_reconfigure_entry()
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_credentials(
            "reauth_confirm", user_input, self._get_reauth_entry()
        )

    async def _async_credentials(
        self,
        step: str,
        user_input: dict[str, Any] | None,
        entry: ConfigEntry | None = None,
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            data = dict(user_input)
            try:
                data[CONF_URL] = normalize_url(data[CONF_URL])
                if not data[CONF_USERNAME].strip() or not data[CONF_PASSWORD]:
                    raise ValueError
                if any(
                    other.entry_id != (entry.entry_id if entry else None)
                    and other.data[CONF_URL] == data[CONF_URL]
                    for other in self._async_current_entries()
                ):
                    return self.async_abort(reason="already_configured")
                await TuliproxClient(
                    async_get_clientsession(self.hass),
                    data[CONF_URL],
                    data[CONF_USERNAME],
                    data[CONF_PASSWORD],
                ).async_snapshot()
                
                # Validate Xtream credentials if provided
                xtream_username = data.get(CONF_XTREAM_USERNAME, "").strip()
                xtream_password = data.get(CONF_XTREAM_PASSWORD, "").strip()
                if xtream_username and xtream_password:
                    from .xtream import XtreamClient
                    try:
                        await XtreamClient(
                            async_get_clientsession(self.hass),
                            data[CONF_URL],
                            xtream_username,
                            xtream_password,
                        ).async_get_user_info()
                    except Exception:
                        errors["base"] = "invalid_xtream_auth"
                        # Still allow setup without Xtream
                        data.pop(CONF_XTREAM_USERNAME, None)
                        data.pop(CONF_XTREAM_PASSWORD, None)
                        
            except ValueError:
                errors["base"] = "invalid_input"
            except TuliproxAuthError:
                errors["base"] = "invalid_auth"
            except TuliproxError:
                errors["base"] = "cannot_connect"
            else:
                if entry is not None:
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates=data,
                        reason="reauth_successful"
                        if step == "reauth_confirm"
                        else "reconfigure_successful",
                    )
                return self.async_create_entry(title="Tuliprox", data=data)
        defaults = user_input or (entry.data if entry else {})
        # Never send the saved password back as a form default.
        return self.async_show_form(
            step_id=step,
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL, default=defaults.get(CONF_URL, "")
                    ): TextSelector(),
                    vol.Required(
                        CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
                    ): TextSelector(),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                    vol.Optional(
                        CONF_XTREAM_USERNAME,
                        default=defaults.get(CONF_XTREAM_USERNAME, ""),
                    ): TextSelector(),
                    vol.Optional(
                        CONF_XTREAM_PASSWORD,
                    ): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
        )


class TuliproxOptionsFlow(OptionsFlowWithReload):
    """Polling interval and exact, case-sensitive usernames to track."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            users = list(
                dict.fromkeys(
                    name.strip()
                    for name in user_input[CONF_TRACKED_USERS].split(",")
                    if name.strip()
                )
            )
            if len(users) > 20 or any(
                safe_text(name) != name or len(name) > 64 for name in users
            ):
                errors["base"] = "invalid_users"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_INTERVAL: user_input[CONF_INTERVAL],
                        CONF_TRACKED_USERS: users,
                    },
                )
        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INTERVAL,
                        default=options.get(CONF_INTERVAL, DEFAULT_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                    vol.Required(
                        CONF_TRACKED_USERS,
                        default=",".join(
                            options.get(CONF_TRACKED_USERS, DEFAULT_TRACKED_USERS)
                        ),
                    ): str,
                }
            ),
        )
