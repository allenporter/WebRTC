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


from . import utils
from .utils import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera"]

BINARY_VERSION = 'v5'

CREATE_LINK_SCHEMA = vol.Schema(
    {
        vol.Required('link_id'): cv.string,
        vol.Exclusive('url', 'url'): cv.string,
        vol.Exclusive('entity', 'url'): cv.entity_id,
        vol.Optional('open_limit', default=1): cv.positive_int,
        vol.Optional('time_to_live', default=60): cv.positive_int,
    },
    required=True,
)

DASH_CAST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Exclusive('url', 'url'): cv.string,
        vol.Exclusive('entity', 'url'): cv.entity_id,
    },
    required=True,
)

LINKS = {}  # 2 3 4

SERVER_URL = "https://rtsp-to-webrtc.dev.mrv.thebends.org/"


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    # serve lovelace card
    async def create_link(call: ServiceCallType):
        link_id = call.data['link_id']
        ttl = call.data['time_to_live']
        LINKS[link_id] = {
            'url': call.data.get('url'),
            'entity': call.data.get('entity'),
            'limit': call.data['open_limit'],
            'ts': time.time() + ttl if ttl else 0
        }

    async def dash_cast(call: ServiceCallType):
        link_id = uuid.uuid4().hex
        LINKS[link_id] = {
            'url': call.data.get('url'),
            'entity': call.data.get('entity'),
            'limit': 1,  # 1 attempt
            'ts': time.time() + 30  # for 30 seconds
        }

        await hass.async_add_executor_job(
            utils.dash_cast, hass,
            call.data[ATTR_ENTITY_ID],
            f"{get_url(hass)}/webrtc/embed?url={link_id}"
        )

    hass.services.async_register(DOMAIN, 'create_link', create_link,
                                 CREATE_LINK_SCHEMA)
    hass.services.async_register(DOMAIN, 'dash_cast', dash_cast,
                                 DASH_CAST_SCHEMA)

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

