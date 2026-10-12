"""Analysis grid shared by every raster in a run (Phase 0, frozen).

One run = one grid: local UTM zone of the AOI centroid, 10 m pixels, origin snapped
to whole multiples of the pixel size. The pipeline writes grid.json first; every
stage reads it and writes rasters with exactly this CRS, transform and shape.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from affine import Affine
from pyproj import CRS, Transformer

from cutoff.contracts import PIXEL_M


def utm_epsg(lon: float, lat: float) -> int:
    """EPSG code of the WGS84 / UTM zone containing (lon, lat). Trishuli (85.3E, 28.1N) -> 32645."""
    zone = int((lon + 180.0) // 6.0) + 1
    return (32600 if lat >= 0 else 32700) + zone


@dataclass(frozen=True)
class Grid:
    epsg: int
    transform: tuple[float, float, float, float, float, float]  # affine a, b, c, d, e, f
    width: int
    height: int

    @property
    def crs(self) -> CRS:
        return CRS.from_epsg(self.epsg)

    @property
    def affine(self) -> Affine:
        return Affine(*self.transform)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(left, bottom, right, top) in grid CRS metres."""
        a = self.affine
        return (a.c, a.f + a.e * self.height, a.c + a.a * self.width, a.f)

    def bounds_wgs84(self) -> tuple[float, float, float, float]:
        """(west, south, east, north) degrees - the envelope of the grid."""
        left, bottom, right, top = self.bounds
        t = Transformer.from_crs(self.epsg, 4326, always_xy=True)
        xs, ys = t.transform([left, left, right, right], [bottom, top, bottom, top])
        return (min(xs), min(ys), max(xs), max(ys))

    def profile(self, dtype: str, count: int = 1, nodata=None) -> dict:
        """rasterio write profile for a raster on this grid."""
        return {
            "driver": "GTiff", "dtype": dtype, "count": count, "nodata": nodata,
            "width": self.width, "height": self.height, "crs": self.crs, "transform": self.affine,
            "compress": "deflate", "tiled": True, "blockxsize": 256, "blockysize": 256,
        }

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=1))

    @classmethod
    def from_json(cls, path: str | Path) -> "Grid":
        d = json.loads(Path(path).read_text())
        return cls(epsg=int(d["epsg"]), transform=tuple(d["transform"]),
                   width=int(d["width"]), height=int(d["height"]))


def make_grid(bbox_wgs84: tuple[float, float, float, float], res: float = PIXEL_M,
              buffer_m: float = 0.0) -> Grid:
    """Grid covering bbox (W, S, E, N in degrees), snapped outward to multiples of `res`."""
    w, s, e, n = bbox_wgs84
    if not (w < e and s < n):
        raise ValueError(f"bbox must be W,S,E,N with W<E and S<N, got {bbox_wgs84}")
    epsg = utm_epsg((w + e) / 2.0, (s + n) / 2.0)
    t = Transformer.from_crs(4326, epsg, always_xy=True)
    xs, ys = t.transform([w, w, e, e], [s, n, s, n])
    left = math.floor((min(xs) - buffer_m) / res) * res
    right = math.ceil((max(xs) + buffer_m) / res) * res
    bottom = math.floor((min(ys) - buffer_m) / res) * res
    top = math.ceil((max(ys) + buffer_m) / res) * res
    width, height = int(round((right - left) / res)), int(round((top - bottom) / res))
    return Grid(epsg=epsg, transform=(res, 0.0, left, 0.0, -res, top), width=width, height=height)
