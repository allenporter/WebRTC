import asyncio
import logging
import os
import stat
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlencode

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import web
from aiohttp.web_exceptions import HTTPUnauthorized, HTTPGone, HTTPNotFound
from homeassistant.components.camera import SUPPORT_STREAM, Camera
from homeassistant.components.camera.const import STREAM_TYPE_HLS, STREAM_TYPE_WEB_RTC
from homeassistant.helpers.entity_component import EntityComponent, \
    DATA_INSTANCES
from homeassistant.components.hassio.ingress import _websocket_forward
from homeassistant.components.http import HomeAssistantView, KEY_AUTHENTICATED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, ATTR_ENTITY_ID
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url
from homeassistant.helpers.typing import HomeAssistantType, ConfigType, \
    ServiceCallType
from homeassistant.helpers.entity import DeviceInfo


_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera"]

BINARY_VERSION = 'v5'


DASH_CAST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Exclusive('url', 'url'): cv.string,
        vol.Exclusive('entity', 'url'): cv.entity_id,
    },
    required=True,
)

LINKS = {}  # 2 3 4


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    return True

async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    # add options handler
    if not entry.update_listeners:
        entry.add_update_listener(async_update_options)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    return True


async def async_update_options(hass: HomeAssistantType, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)

