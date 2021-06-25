from __future__ import annotations

import logging
from typing import Any

import requests
import base64

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_API_TOKEN,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default="8000"): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigurationHub:
    def __init__(self, host: str, port: str) -> None:
        self.host = host
        self.port = port
        self.apikey = ""

    def authenticate(self, username: str, password: str) -> bool:
        url = f"http://" + self.host + ":" + self.port + "/api/token/?format=json"
        headers = {"Accept": "application/json; version=2"}
        resp = requests.post(
            url, headers=headers, data={"username": username, "password": password}
        )
        if resp.status_code == 403:
            _LOGGER.debug(
                f"Expected 200 return got {resp.status_code} {resp.raw} {resp.headers}"
            )
            raise InvalidAuth
        elif resp.status_code != 200:
            _LOGGER.debug(
                f"Expected 200 return got {resp.status_code} {resp.raw} {resp.headers}"
            )
            raise CannotConnect
        try:
            self.apikey = resp.json()["token"]
            _LOGGER.debug(f"Got API Key for Paperless {self.apikey}")
        except:
            raise InvalidAuth
        return True

    def gettoken(self) -> str:
        return self.apikey


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    hub = ConfigurationHub(data[CONF_HOST], data[CONF_PORT])
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )
    if not await hass.async_add_executor_job(
        hub.authenticate, data[CONF_USERNAME], data[CONF_PASSWORD]
    ):
        return InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": "Paperless-NG Configuration", "api_token": hub.gettoken()}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=info["title"],
                data={
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_API_TOKEN: info[CONF_API_TOKEN],
                },
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
