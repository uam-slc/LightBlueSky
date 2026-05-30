"""Overture Buildings normalization and GeoParquet writing."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from statistics import median
from typing import Any, Mapping

from .terrain import TerrainCogSampler


BUILDING_COLUMNS = [
    "id",
    "geometry",
    "height_m",
    "height_source",
    "height_confidence",
    "base_h_ellipsoid_m",
    "top_h_ellipsoid_m",
    "terrain_sample_method",
    "source",
    "properties_json",
]

HEIGHT_FIELDS = ("height", "height_m")
FLOOR_FIELDS = ("num_floors", "numFloors", "levels", "floors")


@dataclass(frozen=True)
class HeightEstimate:
    height_m: float | None
    height_source: str
    height_confidence: str


@dataclass(frozen=True)
class TerrainBaseSample:
    base_h_ellipsoid_m: float | None
    terrain_sample_method: str


def normalize_height_record(
    record: Mapping[str, Any],
    *,
    floor_height_m: float = 3.0,
) -> HeightEstimate:
    """Normalize Overture building height fields to meters."""

    for field in HEIGHT_FIELDS:
        height = _positive_float(record.get(field))
        if height is not None:
            return HeightEstimate(height, field, "high")

    for field in FLOOR_FIELDS:
        floors = _positive_float(record.get(field))
        if floors is not None:
            return HeightEstimate(floors * floor_height_m, "num_floors", "medium")

    return HeightEstimate(None, "missing", "none")


def compute_top_height(
    base_h_ellipsoid_m: float | None, height_m: float | None
) -> float | None:
    if base_h_ellipsoid_m is None or height_m is None:
        return None
    return float(base_h_ellipsoid_m) + float(height_m)


def sample_base_height_for_geometry(
    geometry: Any,
    terrain_sampler: TerrainCogSampler,
    *,
    method: str = "footprint_points_median",
) -> TerrainBaseSample:
    """Estimate building base height from terrain under the footprint."""

    points = _footprint_sample_points(geometry)
    values = []
    for point in points:
        value = terrain_sampler.sample(float(point.x), float(point.y))
        if value is not None:
            values.append(float(value))

    if not values:
        return TerrainBaseSample(None, f"{method}:no_valid_terrain_sample")

    if method == "footprint_points_low_quantile":
        base = _quantile(values, 0.25)
    else:
        base = median(values)
    return TerrainBaseSample(float(base), f"{method}:n={len(values)}")


def build_buildings_geodataframe(
    overture_buildings_path: str | Path,
    terrain_cog_paths: list[str | Path],
    *,
    floor_height_m: float = 3.0,
    terrain_sample_method: str = "footprint_points_median",
) -> Any:
    """Read Overture buildings, normalize heights, and sample base heights."""

    gpd = _require_geopandas()
    buildings = gpd.read_parquet(overture_buildings_path)
    if buildings.crs is None:
        buildings = buildings.set_crs("EPSG:4326")
    else:
        buildings = buildings.to_crs("EPSG:4326")

    output = buildings.copy()
    height_values: list[float | None] = []
    height_sources: list[str] = []
    height_confidences: list[str] = []
    base_values: list[float | None] = []
    top_values: list[float | None] = []
    sample_methods: list[str] = []
    properties_json: list[str] = []

    with TerrainCogSampler(terrain_cog_paths) as terrain_sampler:
        for _, row in output.iterrows():
            record = row.to_dict()
            height = normalize_height_record(record, floor_height_m=floor_height_m)
            base = sample_base_height_for_geometry(
                row.geometry,
                terrain_sampler,
                method=terrain_sample_method,
            )

            height_values.append(height.height_m)
            height_sources.append(height.height_source)
            height_confidences.append(height.height_confidence)
            base_values.append(base.base_h_ellipsoid_m)
            top_values.append(
                compute_top_height(base.base_h_ellipsoid_m, height.height_m)
            )
            sample_methods.append(base.terrain_sample_method)
            properties_json.append(_properties_json(record))

    if "id" not in output.columns:
        output["id"] = [str(index) for index in output.index]
    output["height_m"] = height_values
    output["height_source"] = height_sources
    output["height_confidence"] = height_confidences
    output["base_h_ellipsoid_m"] = base_values
    output["top_h_ellipsoid_m"] = top_values
    output["terrain_sample_method"] = sample_methods
    output["source"] = "Overture Maps Buildings"
    output["properties_json"] = properties_json
    return output[BUILDING_COLUMNS]


def write_buildings_geoparquet(buildings: Any, output_path: str | Path) -> Path:
    """Write normalized buildings as GeoParquet."""

    missing = [column for column in BUILDING_COLUMNS if column not in buildings.columns]
    if missing:
        raise ValueError(f"Missing required building columns: {missing}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    buildings[BUILDING_COLUMNS].to_parquet(output_path, index=False)
    return output_path


def convert_overture_buildings_to_geoparquet(
    overture_buildings_path: str | Path,
    terrain_cog_paths: list[str | Path],
    output_path: str | Path,
    *,
    floor_height_m: float = 3.0,
    terrain_sample_method: str = "footprint_points_median",
) -> Path:
    buildings = build_buildings_geodataframe(
        overture_buildings_path,
        terrain_cog_paths,
        floor_height_m=floor_height_m,
        terrain_sample_method=terrain_sample_method,
    )
    return write_buildings_geoparquet(buildings, output_path)


def _positive_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _footprint_sample_points(geometry: Any, *, max_vertices: int = 32) -> list[Any]:
    if geometry is None or geometry.is_empty:
        return []

    points = [geometry.representative_point(), geometry.centroid]
    polygons = list(_iter_polygons(geometry))
    for polygon in polygons:
        coords = list(polygon.exterior.coords)
        if not coords:
            continue
        step = max(1, len(coords) // max_vertices)
        points.extend(_point_xy(x, y) for x, y in coords[::step])

    unique = []
    seen = set()
    for point in points:
        key = (round(float(point.x), 12), round(float(point.y), 12))
        if key in seen:
            continue
        seen.add(key)
        unique.append(point)
    return unique


def _iter_polygons(geometry: Any):
    if geometry.geom_type == "Polygon":
        yield geometry
    elif geometry.geom_type == "MultiPolygon":
        yield from geometry.geoms


def _point_xy(x: float, y: float) -> Any:
    try:
        from shapely.geometry import Point
    except ImportError as exc:
        raise ImportError("shapely is required for building footprint sampling") from exc
    return Point(float(x), float(y))


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot compute quantile of an empty value list")
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[index]


def _properties_json(record: Mapping[str, Any]) -> str:
    properties = {
        key: value
        for key, value in record.items()
        if key not in set(BUILDING_COLUMNS) | {"geometry"}
    }
    return json.dumps(properties, ensure_ascii=True, sort_keys=True, default=str)


def _require_geopandas():
    try:
        import geopandas as gpd
    except ImportError as exc:
        raise ImportError("geopandas is required for building GeoParquet IO") from exc
    return gpd
