"""FABDEM terrain conversion to WGS84 ellipsoid-height COG files."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .geoid import GeoidProvider, get_default_geoid_provider


TERRAIN_BAND_NAME = "terrain_h_ellipsoid_m"
TERRAIN_METADATA = {
    "coordinate_order": "lon_lat",
    "height_unit": "meter",
    "vertical_datum": "WGS84_ELLIPSOID",
    "source": "FABDEM",
    "source_vertical_datum": "EGM2008",
    "geoid_model": "EGM2008",
}


def _require_numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise ImportError("numpy is required for terrain conversion") from exc
    return np


def _require_rasterio():
    try:
        import rasterio
    except ImportError as exc:
        raise ImportError("rasterio is required for terrain COG IO") from exc
    return rasterio


def fabdem_orthometric_to_ellipsoid(
    fabdem_height_m: Any,
    geoid_separation_m: Any,
    *,
    nodata: float | None = None,
) -> Any:
    """Convert FABDEM orthometric height to WGS84 ellipsoid height.

    ``terrain_h_ellipsoid_m = H_fabdem_m + N_egm2008_m``.
    """

    if isinstance(fabdem_height_m, (int, float)) and isinstance(
        geoid_separation_m, (int, float)
    ):
        if nodata is not None and float(fabdem_height_m) == float(nodata):
            return nodata
        return float(fabdem_height_m) + float(geoid_separation_m)

    np = _require_numpy()
    fabdem = np.asarray(fabdem_height_m, dtype="float64")
    geoid = np.asarray(geoid_separation_m, dtype="float64")
    result = fabdem + geoid
    if nodata is not None:
        result = np.where(fabdem == float(nodata), float(nodata), result)
    return result


def pixel_center_lon_lat(transform: Any, width: int, height: int) -> tuple[Any, Any]:
    """Return lon and lat arrays for raster pixel centers."""

    np = _require_numpy()
    rows, cols = np.indices((height, width), dtype="float64")
    cols = cols + 0.5
    rows = rows + 0.5
    lon = transform.c + cols * transform.a + rows * transform.b
    lat = transform.f + cols * transform.d + rows * transform.e
    return lon, lat


def geoid_grid_for_raster(
    lon: Any,
    lat: Any,
    valid_mask: Any,
    geoid_provider: GeoidProvider,
) -> Any:
    """Evaluate geoid separation for valid raster pixels."""

    np = _require_numpy()
    geoid = np.full(lon.shape, np.nan, dtype="float64")
    valid_lat = lat[valid_mask].ravel()
    valid_lon = lon[valid_mask].ravel()

    if hasattr(geoid_provider, "separations"):
        values = geoid_provider.separations(valid_lat.tolist(), valid_lon.tolist())
        geoid[valid_mask] = np.asarray(values, dtype="float64")
        return geoid

    values = [
        geoid_provider.separation(float(point_lat), float(point_lon))
        for point_lat, point_lon in zip(valid_lat, valid_lon, strict=True)
    ]
    geoid[valid_mask] = np.asarray(values, dtype="float64")
    return geoid


def write_terrain_cog(
    output_path: str | Path,
    terrain_h_ellipsoid_m: Any,
    *,
    transform: Any,
    crs: str = "EPSG:4326",
    nodata: float | None = None,
    extra_tags: dict[str, str] | None = None,
) -> Path:
    """Write a terrain WGS84 ellipsoid-height raster as a COG."""

    np = _require_numpy()
    rasterio = _require_rasterio()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = np.asarray(terrain_h_ellipsoid_m, dtype="float32")
    profile = {
        "driver": "COG",
        "height": data.shape[0],
        "width": data.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
        "compress": "DEFLATE",
        "overview_resampling": "nearest",
    }

    try:
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(data, 1)
            _tag_terrain_dataset(dst, extra_tags=extra_tags)
    except Exception:
        profile.update(
            {
                "driver": "GTiff",
                "tiled": True,
                "blockxsize": 256,
                "blockysize": 256,
                "predictor": 3,
            }
        )
        profile.pop("overview_resampling", None)
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(data, 1)
            _tag_terrain_dataset(dst, extra_tags=extra_tags)

    return output_path


def convert_fabdem_tile_to_ellipsoid_cog(
    fabdem_tile_path: str | Path,
    output_path: str | Path,
    *,
    geoid_provider: GeoidProvider | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> Path:
    """Convert one FABDEM tile to an EPSG:4326 ellipsoid-height COG."""

    np = _require_numpy()
    rasterio = _require_rasterio()
    geoid_provider = geoid_provider or get_default_geoid_provider()

    with rasterio.open(fabdem_tile_path) as src:
        nodata = src.nodata
        if src.crs and str(src.crs).upper() not in {"EPSG:4326", "OGC:CRS84"}:
            from rasterio.warp import Resampling, calculate_default_transform, reproject

            transform, width, height = calculate_default_transform(
                src.crs, "EPSG:4326", src.width, src.height, *src.bounds
            )
            data = np.full((height, width), nodata if nodata is not None else np.nan)
            reproject(
                source=rasterio.band(src, 1),
                destination=data,
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=nodata,
                dst_transform=transform,
                dst_crs="EPSG:4326",
                dst_nodata=nodata,
                resampling=Resampling.bilinear,
            )
        else:
            transform = src.transform
            if bbox is None:
                data = src.read(1).astype("float64")
            else:
                from rasterio.windows import from_bounds

                min_lon, min_lat, max_lon, max_lat = bbox
                window = from_bounds(
                    min_lon,
                    min_lat,
                    max_lon,
                    max_lat,
                    transform=src.transform,
                )
                window = window.round_offsets().round_lengths()
                data = src.read(1, window=window).astype("float64")
                transform = src.window_transform(window)

    valid_mask = _valid_terrain_mask(data, nodata)
    lon, lat = pixel_center_lon_lat(transform, data.shape[1], data.shape[0])
    geoid = geoid_grid_for_raster(lon, lat, valid_mask, geoid_provider)
    terrain = fabdem_orthometric_to_ellipsoid(data, geoid, nodata=nodata)
    if nodata is not None:
        terrain = np.where(valid_mask, terrain, nodata)

    return write_terrain_cog(
        output_path,
        terrain,
        transform=transform,
        crs="EPSG:4326",
        nodata=nodata,
    )


class TerrainCogSampler:
    """Sample one or more terrain COG files by lon/lat."""

    def __init__(self, terrain_paths: Iterable[str | Path]):
        rasterio = _require_rasterio()
        self._rasterio = rasterio
        self._datasets = [rasterio.open(path) for path in terrain_paths]

    def close(self) -> None:
        for dataset in self._datasets:
            dataset.close()

    def __enter__(self) -> "TerrainCogSampler":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def sample(self, lon: float, lat: float) -> float | None:
        for dataset in self._datasets:
            bounds = dataset.bounds
            if not (bounds.left <= lon <= bounds.right and bounds.bottom <= lat <= bounds.top):
                continue
            value = next(dataset.sample([(lon, lat)]))[0]
            nodata = dataset.nodata
            if nodata is not None and float(value) == float(nodata):
                continue
            try:
                import math

                if math.isnan(float(value)):
                    continue
            except TypeError:
                continue
            return float(value)
        return None


def _valid_terrain_mask(data: Any, nodata: float | None) -> Any:
    np = _require_numpy()
    valid_mask = np.isfinite(data)
    if nodata is not None:
        valid_mask &= data != float(nodata)
    return valid_mask


def _tag_terrain_dataset(dataset: Any, *, extra_tags: dict[str, str] | None = None) -> None:
    tags = dict(TERRAIN_METADATA)
    if extra_tags:
        tags.update(extra_tags)
    dataset.set_band_description(1, TERRAIN_BAND_NAME)
    dataset.update_tags(**tags)
    dataset.update_tags(1, band_name=TERRAIN_BAND_NAME)
