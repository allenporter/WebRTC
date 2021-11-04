import json
import logging
import platform
import subprocess
from threading import Thread
from typing import Optional

from aiohttp import web
from homeassistant.components.camera import Camera
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.lovelace.resources import \
    ResourceStorageCollection
from homeassistant.helpers.entity_component import EntityComponent, \
    DATA_INSTANCES
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'webrtc'

SYSTEM = {
    'Windows': 'amd64.exe',
    'Darwin': 'darwin',
    'FreeBSD': 'freebsd',
    'Linux': {
        'armv7l': 'armv7',
        'armv8l': 'armv7',  # https://github.com/AlexxIT/WebRTC/issues/18
        'aarch64': 'aarch64',
        'x86_64': 'amd64',
        'i386': 'i386',
        'i486': 'i386',
        'i586': 'i386',
        'i686': 'i386',
    }
}


def get_arch() -> Optional[str]:
    system = SYSTEM.get(platform.system())
    if isinstance(system, dict):
        return system.get(platform.machine())
    elif system:
        return system
    return None
