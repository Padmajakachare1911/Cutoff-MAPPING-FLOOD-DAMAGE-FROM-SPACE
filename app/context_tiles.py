"""Cached historical Sentinel-2 context; never an event observation or model input."""
from __future__ import annotations

import io
import uuid
from pathlib import Path

import requests
from PIL import Image

ATTRIBUTION = ('<a href="https://cloudless.eox.at/">EOxCloudless</a> by '
               '<a href="https://eox.at/">EOX IT Services GmbH</a> '
               '(Contains modified Copernicus Sentinel data 2025); CC BY-NC-SA 4.0')


def historical_tile(cache: Path, z: int, x: int, y: int) -> bytes:
    if not (0 <= z <= 15 and 0 <= x < 2**z and 0 <= y < 2**z):
        raise ValueError('Invalid historical context tile')
    root = cache / 'display_context' / 's2cloudless-2025' / str(z) / str(x)
    path = root / f'{y}.jpg'
    if path.exists():
        return path.read_bytes()
    url = f'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2025_3857/default/g/{z}/{y}/{x}.jpg'
    response = requests.get(url, timeout=(5, 15))
    response.raise_for_status()
    with Image.open(io.BytesIO(response.content)) as image:
        if image.format != 'JPEG' or image.size != (256, 256):
            raise ValueError('Invalid historical Sentinel-2 context response')
    root.mkdir(parents=True, exist_ok=True)
    temp = root / f'{y}.{uuid.uuid4().hex}.tmp'
    temp.write_bytes(response.content)
    temp.replace(path)
    return response.content
