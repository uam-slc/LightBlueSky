"""Dataset folder creation and read helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .terrain import TerrainCogSampler


DATASET_NAME = "global_wgs84_ellipsoid_3d_map"
SCHEMA_VERSION = "1.0.0"


def create_dataset_folder(
    path: str | Path = DATASET_NAME,
    *,
    created_at: str | None = None,
    floor_height_m: float = 3.0,
    terrain_tile_scheme: str = "source FABDEM tile id, emitted as <terrain_tile_id>.cog.tif",
    building_partition_scheme: str = (
        "source Overture partition id, emitted as <building_partition_id>.geoparquet"
    ),
    generation_parameters: dict[str, Any] | None = None,
    license_and_attribution: dict[str, Any] | None = None,
) -> Path:
    """Create the final dataset folder scaffold and write its contracts."""

    root = Path(path)
    (root / "terrain").mkdir(parents=True, exist_ok=True)
    (root / "buildings").mkdir(parents=True, exist_ok=True)
    write_manifest(
        root / "manifest.json",
        created_at=created_at,
        floor_height_m=floor_height_m,
        terrain_tile_scheme=terrain_tile_scheme,
        building_partition_scheme=building_partition_scheme,
        generation_parameters=generation_parameters,
        license_and_attribution=license_and_attribution,
    )
    write_readme(root / "README.md")
    return root


def write_manifest(
    output_path: str | Path,
    *,
    created_at: str | None = None,
    floor_height_m: float = 3.0,
    terrain_tile_scheme: str = "source FABDEM tile id, emitted as <terrain_tile_id>.cog.tif",
    building_partition_scheme: str = (
        "source Overture partition id, emitted as <building_partition_id>.geoparquet"
    ),
    generation_parameters: dict[str, Any] | None = None,
    license_and_attribution: dict[str, Any] | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at or _utc_now(),
        "dataset_name": DATASET_NAME,
        "dataset_scope": "global",
        "horizontal_crs": "EPSG:4326",
        "coordinate_order": "lon_lat",
        "vertical_datum": "WGS84_ELLIPSOID",
        "height_unit": "meter",
        "terrain_dir": "terrain/",
        "buildings_dir": "buildings/",
        "terrain_source": "FABDEM",
        "buildings_source": "Overture Maps Buildings",
        "geoid_model": "EGM2008",
        "geoid_provider": "GeographicLib",
        "floor_height_m": floor_height_m,
        "terrain_tile_scheme": terrain_tile_scheme,
        "building_partition_scheme": building_partition_scheme,
        "generation_parameters": generation_parameters or {
            "terrain_height_formula": "terrain_h_ellipsoid_m = H_fabdem_m + N_egm2008_m",
            "building_top_formula": "top_h_ellipsoid_m = base_h_ellipsoid_m + height_m",
            "terrain_sample_method_default": "footprint_points_median",
        },
        "license_and_attribution": license_and_attribution or {
            "FABDEM": "Retain FABDEM license and attribution from the source distribution.",
            "Overture Maps Buildings": (
                "Retain Overture Maps license and attribution from the source release."
            ),
            "EGM2008": "Retain GeographicLib and EGM2008 model attribution.",
        },
    }
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output_path


def write_readme(output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(readme_text(), encoding="utf-8")
    return output_path


def readme_text() -> str:
    return """# global_wgs84_ellipsoid_3d_map

This folder is a global three-dimensional map dataset contract for low-altitude traffic management simulation. It stores terrain and building surfaces in one coordinate and height convention:

- lon: WGS84 longitude.
- lat: WGS84 latitude.
- h_ellipsoid_m: WGS84 ellipsoid height in meters.

## Files

- `README.md`: dataset semantics and field contract.
- `manifest.json`: machine-readable dataset metadata.
- `terrain/<terrain_tile_id>.cog.tif`: terrain Cloud Optimized GeoTIFF tiles.
- `buildings/<building_partition_id>.geoparquet`: building footprint and height partitions.

## Terrain Data

Each terrain COG uses CRS `EPSG:4326`, coordinate order `lon_lat`, and band name `terrain_h_ellipsoid_m`. Pixel values are WGS84 ellipsoid heights in meters:

```text
terrain_h_ellipsoid_m = H_fabdem_m + N_egm2008_m
```

`H_fabdem_m` is the FABDEM source elevation treated as an EGM2008 orthometric height. `N_egm2008_m` is the EGM2008 geoid separation from GeographicLib or a compatible interpolator. NoData values are preserved.

## Buildings Data

Each building GeoParquet partition stores WGS84 lon/lat footprints and building heights aligned to the converted terrain layer. A building record expresses:

```text
footprint_lon_lat, base_h_ellipsoid_m, top_h_ellipsoid_m
```

If an Overture height field exists, it is used as `height_m`. If height is missing and `num_floors` is available, `height_m = num_floors * floor_height_m` with default `floor_height_m = 3.0`. If no height can be derived, the footprint and `base_h_ellipsoid_m` are retained and `top_h_ellipsoid_m` is null.

## Exposed Inputs

- Terrain query input: `lon`, `lat`.
- Building query input: `lon`, `lat`.
- Surface query input: `lon`, `lat`.

All inputs are WGS84 longitude and latitude in degrees. Do not pass local NED, ECEF, projected meters, or latitude-longitude order.

## Exposed Outputs

- Terrain query output: `terrain_h_ellipsoid_m`.
- Building query output: buildings containing the point, including `geometry`, `height_m`, `base_h_ellipsoid_m`, `top_h_ellipsoid_m`, `height_source`, and `height_confidence`.
- Surface query output: `surface_h_ellipsoid_m`.

## Height Definitions

- `terrain_h_ellipsoid_m`: terrain or ground WGS84 ellipsoid height at a lon/lat point.
- `base_h_ellipsoid_m`: building bottom WGS84 ellipsoid height sampled from the terrain layer.
- `height_m`: building height relative to the local ground or base.
- `top_h_ellipsoid_m`: building top WGS84 ellipsoid height.
- `surface_h_ellipsoid_m`: query semantic for the topmost usable surface at a lon/lat point. It is not required to be stored as a field.

The required building top formula is:

```text
top_h_ellipsoid_m = base_h_ellipsoid_m + height_m
```

`top_h_ellipsoid_m` already includes terrain height. Do not add `terrain_h_ellipsoid_m` to `top_h_ellipsoid_m`.

## Terrain Query Semantics

Input:

- `lon`
- `lat`

Output:

- `terrain_h_ellipsoid_m`

Meaning: `terrain_h_ellipsoid_m` is the WGS84 ellipsoid height of the terrain or ground at that lon/lat.

## Building Query Semantics

Input:

- `lon`
- `lat`

Output:

- Building list containing that lon/lat.
- Each building's `geometry`.
- `height_m`.
- `base_h_ellipsoid_m`.
- `top_h_ellipsoid_m`.
- `height_source`.
- `height_confidence`.

Meaning: if lon/lat falls inside a building footprint, the building's `top_h_ellipsoid_m` can be read as that building top WGS84 ellipsoid height when the field is present.

## Surface Height Query Semantics

Given lon/lat:

1. Query `terrain_h_ellipsoid_m`.
2. Query buildings containing the point.
3. If the point falls in one or more building footprints and at least one `top_h_ellipsoid_m` exists:

   ```text
   surface_h_ellipsoid_m = max(top_h_ellipsoid_m)
   ```

4. If the point is not in any building footprint, or all matching buildings have null `top_h_ellipsoid_m`:

   ```text
   surface_h_ellipsoid_m = terrain_h_ellipsoid_m
   ```

If multiple building footprints overlap, `surface_h_ellipsoid_m` uses the highest available `top_h_ellipsoid_m`.

## Terrain Fields

| Field | Meaning |
| --- | --- |
| `lon` | WGS84 longitude. |
| `lat` | WGS84 latitude. |
| `terrain_h_ellipsoid_m` | Terrain WGS84 ellipsoid height in meters. |

## Buildings Fields

| Field | Meaning |
| --- | --- |
| `id` | Building ID. |
| `geometry` | WGS84 lon/lat footprint. |
| `height_m` | Building height relative to ground in meters. |
| `height_source` | Source used for building height. |
| `height_confidence` | Confidence assigned to the building height. |
| `base_h_ellipsoid_m` | Building bottom WGS84 ellipsoid height. |
| `top_h_ellipsoid_m` | Building top WGS84 ellipsoid height. |
| `terrain_sample_method` | Method used to sample building base height from terrain. |
| `source` | Building data source. |
| `properties_json` | Preserved useful original source properties. |

## Fields That Must Not Be Mixed

- Do not mix `terrain_h_ellipsoid_m`, `base_h_ellipsoid_m`, or `top_h_ellipsoid_m` with orthometric heights unless the vertical datum is converted first.
- Do not add `terrain_h_ellipsoid_m` to `top_h_ellipsoid_m`; the top height is already absolute ellipsoid height.
- Do not treat `height_m` as an absolute altitude; it is relative to building base or ground.
- Do not use latitude-longitude order. This dataset uses lon-lat order.
- Do not assume `surface_h_ellipsoid_m` is stored; it is a recommended query result.

## Data Alignment Rules

1. Reproject FABDEM terrain to `EPSG:4326` lon/lat.
2. Use EGM2008 geoid separation to convert FABDEM heights to WGS84 ellipsoid heights.
3. Reproject Overture Buildings footprints to `EPSG:4326` lon/lat.
4. Sample each building's `base_h_ellipsoid_m` from the converted terrain COG.
5. Compute `top_h_ellipsoid_m` from `base_h_ellipsoid_m + height_m`.
6. Record `height_source` and `height_confidence` for each building.
7. Store final terrain and buildings as WGS84 lon/lat plus WGS84 ellipsoid height.

## Format Rationale

Terrain uses Cloud Optimized GeoTIFF because COG supports global tiling, windowed reads, rasterio/GDAL access, georeferencing, metadata, and NoData preservation.

Buildings use GeoParquet because it supports large vector partitions, geometry and attributes, and direct access from geopandas, duckdb, and pyarrow.

## Python Reading Examples

```python
import rasterio

with rasterio.open("global_wgs84_ellipsoid_3d_map/terrain/<terrain_tile_id>.cog.tif") as ds:
    lon, lat = 139.7671, 35.6812
    value = next(ds.sample([(lon, lat)]))[0]
    print("terrain_h_ellipsoid_m:", float(value))
```

```python
import geopandas as gpd

buildings = gpd.read_parquet(
    "global_wgs84_ellipsoid_3d_map/buildings/<building_partition_id>.geoparquet"
)

print(buildings[[
    "id",
    "height_m",
    "base_h_ellipsoid_m",
    "top_h_ellipsoid_m",
]].head())
```
"""


@dataclass
class GlobalWGS84Ellipsoid3DMap:
    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.manifest_path = self.root / "manifest.json"
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Missing dataset manifest: {self.manifest_path}")
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.terrain_paths = sorted((self.root / "terrain").glob("*.cog.tif"))
        self.building_paths = sorted((self.root / "buildings").glob("*.geoparquet"))
        self._terrain_sampler: TerrainCogSampler | None = None
        self._buildings = None

    def close(self) -> None:
        if self._terrain_sampler is not None:
            self._terrain_sampler.close()
            self._terrain_sampler = None

    def __enter__(self) -> "GlobalWGS84Ellipsoid3DMap":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def sample_terrain(self, lon: float, lat: float) -> float:
        """Return terrain_h_ellipsoid_m at lon/lat."""

        if self._terrain_sampler is None:
            self._terrain_sampler = TerrainCogSampler(self.terrain_paths)
        value = self._terrain_sampler.sample(lon, lat)
        if value is None:
            raise ValueError(f"No terrain value found for lon={lon}, lat={lat}")
        return float(value)

    def query_buildings(self, lon: float, lat: float) -> Any:
        """Return buildings whose footprint covers lon/lat."""

        _require_geopandas()
        from shapely.geometry import Point

        buildings = self._load_buildings()
        if buildings.empty:
            return buildings
        point = Point(float(lon), float(lat))
        return buildings[buildings.geometry.covers(point)]

    def sample_surface(self, lon: float, lat: float) -> float:
        """Return surface_h_ellipsoid_m at lon/lat."""

        terrain_h = self.sample_terrain(lon, lat)
        buildings = self.query_buildings(lon, lat)
        if buildings.empty or "top_h_ellipsoid_m" not in buildings.columns:
            return terrain_h

        top_values = buildings["top_h_ellipsoid_m"].dropna()
        if top_values.empty:
            return terrain_h
        return float(top_values.max())

    def _load_buildings(self) -> Any:
        if self._buildings is not None:
            return self._buildings
        gpd = _require_geopandas()
        if not self.building_paths:
            self._buildings = gpd.GeoDataFrame(
                {
                    "id": [],
                    "geometry": [],
                    "height_m": [],
                    "height_source": [],
                    "height_confidence": [],
                    "base_h_ellipsoid_m": [],
                    "top_h_ellipsoid_m": [],
                    "terrain_sample_method": [],
                    "source": [],
                    "properties_json": [],
                },
                geometry="geometry",
                crs="EPSG:4326",
            )
            return self._buildings

        frames = [gpd.read_parquet(path).to_crs("EPSG:4326") for path in self.building_paths]
        self._buildings = gpd.GeoDataFrame(
            __import__("pandas").concat(frames, ignore_index=True),
            geometry="geometry",
            crs="EPSG:4326",
        )
        return self._buildings


def open_dataset(path: str | Path) -> GlobalWGS84Ellipsoid3DMap:
    return GlobalWGS84Ellipsoid3DMap(Path(path))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _require_geopandas():
    try:
        import geopandas as gpd
    except ImportError as exc:
        raise ImportError("geopandas is required for building queries") from exc
    return gpd
