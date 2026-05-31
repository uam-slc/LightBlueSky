"""Overture Buildings normalization and GeoParquet writing."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
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

    buildings = _read_overture_buildings(overture_buildings_path)
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


def write_aligned_buildings_from_overture_parquet_streaming(
    overture_buildings_path: str | Path,
    terrain_cog_paths: list[str | Path],
    output_path: str | Path,
    *,
    floor_height_m: float = 3.0,
    batch_size: int = 250_000,
) -> Path:
    """Stream-align large Overture parquet files without loading all geometry.

    The production path uses the Overture bbox center as the terrain sample
    point. This keeps very large regional extracts tractable while preserving
    the final dataset contract.
    """

    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    terrain_index = _RasterTerrainIndex(terrain_cog_paths)

    source = pq.ParquetFile(overture_buildings_path)
    geo_metadata = _geo_metadata_for_output(source.schema_arrow.metadata or {})
    schema = pa.schema(
        [
            ("id", pa.string()),
            ("geometry", pa.binary()),
            ("height_m", pa.float64()),
            ("height_source", pa.string()),
            ("height_confidence", pa.string()),
            ("base_h_ellipsoid_m", pa.float64()),
            ("top_h_ellipsoid_m", pa.float64()),
            ("terrain_sample_method", pa.string()),
            ("source", pa.string()),
            ("properties_json", pa.string()),
        ],
        metadata=geo_metadata,
    )

    columns = ["id", "geometry", "height", "num_floors", "bbox", "subtype", "class"]
    with pq.ParquetWriter(
        output_path,
        schema=schema,
        compression="zstd",
        use_dictionary=True,
    ) as writer:
        for batch in source.iter_batches(batch_size=batch_size, columns=columns):
            n = batch.num_rows
            names = batch.schema.names
            id_array = batch.column(names.index("id"))
            geometry_array = batch.column(names.index("geometry"))
            bbox_array = batch.column(names.index("bbox"))
            height = _arrow_numeric_column(batch, names, "height", n)
            num_floors = _arrow_numeric_column(batch, names, "num_floors", n)
            subtype = _arrow_string_column(batch, names, "subtype", n)
            class_name = _arrow_string_column(batch, names, "class", n)

            xmin = bbox_array.field("xmin").to_numpy(zero_copy_only=False)
            xmax = bbox_array.field("xmax").to_numpy(zero_copy_only=False)
            ymin = bbox_array.field("ymin").to_numpy(zero_copy_only=False)
            ymax = bbox_array.field("ymax").to_numpy(zero_copy_only=False)
            lon = (xmin + xmax) / 2.0
            lat = (ymin + ymax) / 2.0
            base = terrain_index.sample_many(lon, lat)

            height_valid = np.isfinite(height) & (height > 0)
            floors_valid = np.isfinite(num_floors) & (num_floors > 0)
            height_m = np.full(n, np.nan, dtype="float64")
            height_m[height_valid] = height[height_valid]
            floor_only = ~height_valid & floors_valid
            height_m[floor_only] = num_floors[floor_only] * float(floor_height_m)

            top = np.full(n, np.nan, dtype="float64")
            top_valid = np.isfinite(base) & np.isfinite(height_m)
            top[top_valid] = base[top_valid] + height_m[top_valid]

            height_source = np.full(n, "missing", dtype=object)
            height_source[height_valid] = "height"
            height_source[floor_only] = "num_floors"
            height_confidence = np.full(n, "none", dtype=object)
            height_confidence[height_valid] = "high"
            height_confidence[floor_only] = "medium"
            sample_method = np.full(n, "bbox_center_pixel", dtype=object)
            source_name = np.full(n, "Overture Maps Buildings", dtype=object)
            properties = [
                _stream_properties_json(subtype[i], class_name[i])
                for i in range(n)
            ]

            table = pa.table(
                {
                    "id": id_array,
                    "geometry": geometry_array,
                    "height_m": pa.array(
                        height_m,
                        mask=~np.isfinite(height_m),
                        type=pa.float64(),
                    ),
                    "height_source": pa.array(height_source, type=pa.string()),
                    "height_confidence": pa.array(
                        height_confidence, type=pa.string()
                    ),
                    "base_h_ellipsoid_m": pa.array(
                        base,
                        mask=~np.isfinite(base),
                        type=pa.float64(),
                    ),
                    "top_h_ellipsoid_m": pa.array(
                        top,
                        mask=~np.isfinite(top),
                        type=pa.float64(),
                    ),
                    "terrain_sample_method": pa.array(
                        sample_method, type=pa.string()
                    ),
                    "source": pa.array(source_name, type=pa.string()),
                    "properties_json": pa.array(properties, type=pa.string()),
                },
                schema=schema,
            )
            writer.write_table(table)

    terrain_index.close()
    return output_path


def _positive_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
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


class _RasterTerrainIndex:
    def __init__(self, terrain_paths: list[str | Path]):
        import rasterio

        self.datasets = [rasterio.open(path) for path in terrain_paths]
        self.arrays: dict[int, Any] = {}

    def close(self) -> None:
        for dataset in self.datasets:
            dataset.close()

    def sample_many(self, lon: Any, lat: Any) -> Any:
        import numpy as np

        lon = np.asarray(lon, dtype="float64")
        lat = np.asarray(lat, dtype="float64")
        result = np.full(lon.shape, np.nan, dtype="float64")
        for index, dataset in enumerate(self.datasets):
            bounds = dataset.bounds
            mask = (
                np.isnan(result)
                & (lon >= bounds.left)
                & (lon < bounds.right)
                & (lat > bounds.bottom)
                & (lat <= bounds.top)
            )
            if not np.any(mask):
                continue
            data = self.arrays.get(index)
            if data is None:
                data = dataset.read(1)
                self.arrays[index] = data
            transform = dataset.transform
            cols = np.floor((lon[mask] - transform.c) / transform.a).astype("int64")
            rows = np.floor((lat[mask] - transform.f) / transform.e).astype("int64")
            valid = (
                (rows >= 0)
                & (rows < data.shape[0])
                & (cols >= 0)
                & (cols < data.shape[1])
            )
            sampled = np.full(rows.shape, np.nan, dtype="float64")
            sampled[valid] = data[rows[valid], cols[valid]]
            if dataset.nodata is not None:
                sampled[sampled == float(dataset.nodata)] = np.nan
            result[mask] = sampled
        return result


def _arrow_numeric_column(batch: Any, names: list[str], name: str, n: int) -> Any:
    import numpy as np

    if name not in names:
        return np.full(n, np.nan, dtype="float64")
    values = batch.column(names.index(name)).to_numpy(zero_copy_only=False)
    return values.astype("float64", copy=False)


def _arrow_string_column(batch: Any, names: list[str], name: str, n: int) -> list[Any]:
    if name not in names:
        return [None] * n
    return batch.column(names.index(name)).to_pylist()


def _stream_properties_json(subtype: Any, class_name: Any) -> str:
    props = {}
    if subtype is not None:
        props["subtype"] = subtype
    if class_name is not None:
        props["class"] = class_name
    return json.dumps(props, ensure_ascii=True, sort_keys=True)


def _geo_metadata_for_output(source_metadata: Mapping[bytes, bytes]) -> dict[bytes, bytes]:
    if b"geo" in source_metadata:
        return {b"geo": source_metadata[b"geo"]}
    return {
        b"geo": (
            b'{"version":"1.0.0","primary_column":"geometry","columns":'
            b'{"geometry":{"encoding":"WKB","geometry_types":["Polygon",'
            b'"MultiPolygon"],"crs":null}}}'
        )
    }


def _read_overture_buildings(path: str | Path) -> Any:
    gpd = _require_geopandas()
    try:
        buildings = gpd.read_parquet(path)
        if "geometry" in buildings.columns:
            return buildings
    except Exception:
        pass

    try:
        import pandas as pd
        from shapely import wkb
    except ImportError as exc:
        raise ImportError(
            "pandas and shapely are required to read raw Overture WKB parquet"
        ) from exc

    frame = pd.read_parquet(path)
    if "geometry" not in frame.columns:
        raise ValueError("Overture buildings input must contain a geometry column")
    frame["geometry"] = frame["geometry"].map(_load_wkb_geometry(wkb))
    return gpd.GeoDataFrame(frame, geometry="geometry", crs="EPSG:4326")


def _load_wkb_geometry(wkb_module):
    def load(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, memoryview):
            value = value.tobytes()
        if isinstance(value, bytearray):
            value = bytes(value)
        if isinstance(value, str):
            return wkb_module.loads(bytes.fromhex(value))
        return wkb_module.loads(value)

    return load
