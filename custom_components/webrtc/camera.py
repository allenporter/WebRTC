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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.http import HomeAssistantView, KEY_AUTHENTICATED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, ATTR_ENTITY_ID
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url
from homeassistant.helpers.typing import HomeAssistantType, ConfigType, \
    ServiceCallType
from homeassistant.helpers.entity import DeviceInfo


_LOGGER = logging.getLogger(__name__)

SERVER_URL = "https://rtsp-to-webrtc.dev.mrv.thebends.org"


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the cameras."""
    _LOGGER.info("Loading cameras for WebRTC wrapping")
    if 'camera' not in hass.data:
        _LOGGER.info("Camera not loaded")
        return
    component: EntityComponent = hass.data['camera']
    camera: Camera
    cameras_to_add = []
    for camera in component.entities:
        if not (camera.supported_features & SUPPORT_STREAM):
            continue
        if camera.frontend_stream_type == STREAM_TYPE_WEB_RTC:
            continue
        cameras_to_add.append(WebRtcCamera(camera))
    async_add_entities(cameras_to_add)

class WebRtcCamera(Camera):
    """WebRtcCamera that wraps another camera."""

    def __init__(self, delegate: Camera):
        super().__init__()
        self._delegate = delegate

    @property
    def should_poll(self) -> bool:
        return self._delegate.should_poll

    @property
    def unique_id(self) -> str:
        return f"{self._delegate.unique_id}-webrtc"

    @property
    def name(self) -> str:
        return f"{self._delegate.name} WebRTC"

    @property
    def device_info(self) -> DeviceInfo:
        return self._delegate.device_info

    @property
    def brand(self) -> str:
        return self._delegate.brand

    @property
    def model(self) -> str:
        return self._delegate.model

    @property
    def supported_features(self) -> str:
        return self._delegate.supported_features

    @property
    def frontend_stream_type(self):
        return STREAM_TYPE_WEB_RTC

    async def stream_source(self) -> str:
        return await self._delegate.stream_source()

    async def async_camera_image(
        self, width: int = None, height: int = None
    ) -> bytes:
        return await self._delegate.async_camera_image(width=width, height=height)

    async def async_handle_web_rtc_offer(self, offer_sdp: str) -> str:  #str | None:
        stream_source = await self.stream_source()
        query = urlencode({'url': stream_source, "debug": "1"})
        url = f"{SERVER_URL}/ws?{query}"
        _LOGGER.info(f"offer: {offer_sdp}")
        _LOGGER.info(f"Connecting to {url}")
        try:
            async with async_get_clientsession(self.hass).ws_connect(url) as ws:
                await ws.send_json({'type': 'webrtc', 'sdp': offer_sdp})
                resp = await ws.receive_json(timeout=15)
        except Exception as ex:
            raise HomeAssistantError(f"Failed to send WebRTC offer: {ex}") from ex
        if "error" in resp:
            error = resp["error"]
            raise HomeAssistantError(f"Response from WebRTC server: {error}")
        _LOGGER.info(f"result: {resp}")
        return resp['sdp']

