from __future__ import annotations

import json

import pytest

from lightbluesky_map.buildings import (
    BUILDING_COLUMNS,
    compute_top_height,
    normalize_height_record,
)
from lightbluesky_map.dataset import create_dataset_folder, readme_text
from lightbluesky_map.geoid import ConstantGeoidProvider
from lightbluesky_map.overture import (
    DEFAULT_OVERTURE_RELEASE,
    overture_buildings_bbox_sql,
    overture_buildings_cloud_path,
)
from lightbluesky_map.regions import get_region, parse_bbox
from lightbluesky_map.terrain import (
    convert_fabdem_tile_to_ellipsoid_cog,
    fabdem_orthometric_to_ellipsoid,
)


def test_geoid_provider_returns_configured_separation() -> None:
    provider = ConstantGeoidProvider(42.5)

    assert provider.separation(35.0, 139.0) == 42.5


def test_fabdem_height_converts_to_ellipsoid_height() -> None:
    assert fabdem_orthometric_to_ellipsoid(100.0, 12.25) == 112.25


def test_overture_height_field_is_preferred() -> None:
    estimate = normalize_height_record({"height": 18.5, "num_floors": 20})

    assert estimate.height_m == 18.5
    assert estimate.height_source == "height"
    assert estimate.height_confidence == "high"


def test_overture_num_floors_estimates_height() -> None:
    estimate = normalize_height_record({"num_floors": 4}, floor_height_m=3.0)

    assert estimate.height_m == 12.0
    assert estimate.height_source == "num_floors"
    assert estimate.height_confidence == "medium"


def test_missing_height_is_preserved_as_null_semantics() -> None:
    estimate = normalize_height_record({})

    assert estimate.height_m is None
    assert estimate.height_source == "missing"
    assert estimate.height_confidence == "none"
    assert compute_top_height(10.0, estimate.height_m) is None


def test_building_top_height_is_base_plus_relative_height() -> None:
    assert compute_top_height(55.25, 14.75) == 70.0


def test_manifest_generation(tmp_path) -> None:
    root = create_dataset_folder(
        tmp_path / "global_wgs84_ellipsoid_3d_map",
        created_at="2026-05-31T00:00:00Z",
    )
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["dataset_name"] == "global_wgs84_ellipsoid_3d_map"
    assert manifest["dataset_scope"] == "global"
    assert manifest["horizontal_crs"] == "EPSG:4326"
    assert manifest["coordinate_order"] == "lon_lat"
    assert manifest["vertical_datum"] == "WGS84_ELLIPSOID"
    assert manifest["terrain_source"] == "FABDEM"
    assert manifest["buildings_source"] == "Overture Maps Buildings"
    assert manifest["geoid_model"] == "EGM2008"
    assert manifest["geoid_provider"] == "GeographicLib"
    assert manifest["floor_height_m"] == 3.0


def test_regional_manifest_generation(tmp_path) -> None:
    region = get_region("bth")
    root = create_dataset_folder(
        tmp_path / "global_wgs84_ellipsoid_3d_map",
        created_at="2026-05-31T00:00:00Z",
        dataset_scope="regional",
        region_name=region.name,
        region_title=region.title,
        region_bbox_lon_lat=list(region.bbox),
    )
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["dataset_scope"] == "regional"
    assert manifest["region_name"] == "beijing-tianjin-hebei"
    assert manifest["region_bbox_lon_lat"] == [113.0, 36.0, 120.0, 42.8]


def test_bth_region_declares_required_fabdem_tiles() -> None:
    region = get_region("bth")

    assert region.bbox == (113.0, 36.0, 120.0, 42.8)
    assert region.fabdem_10x10_tile_ids == (
        "N30E110-N40E120",
        "N40E110-N50E120",
    )
    assert parse_bbox("113,36,120,42.8") == region.bbox


def test_overture_cloud_path_and_bbox_sql() -> None:
    cloud_path = overture_buildings_cloud_path(
        release=DEFAULT_OVERTURE_RELEASE,
        provider="azure",
    )
    sql = overture_buildings_bbox_sql(
        cloud_path=cloud_path,
        bbox=(113.0, 36.0, 120.0, 42.8),
        output_path="data/work/bth.geoparquet",
    )

    assert "az://release/2026-05-20.0/theme=buildings/type=building/*.parquet" in sql
    assert "bbox.xmin <= 120.0" in sql
    assert "bbox.xmax >= 113.0" in sql
    assert "bbox.ymin <= 42.8" in sql
    assert "bbox.ymax >= 36.0" in sql


def test_readme_contains_required_semantics() -> None:
    text = readme_text()

    assert "terrain_h_ellipsoid_m = H_fabdem_m + N_egm2008_m" in text
    assert "top_h_ellipsoid_m = base_h_ellipsoid_m + height_m" in text
    assert "surface_h_ellipsoid_m = max(top_h_ellipsoid_m)" in text
    assert "Do not add `terrain_h_ellipsoid_m` to `top_h_ellipsoid_m`" in text
    assert "`height_m` | Building height relative to ground in meters." in text


def test_small_fabdem_fixture_converts_to_terrain_cog(tmp_path) -> None:
    np = pytest.importorskip("numpy")
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    source_path = tmp_path / "fabdem.tif"
    output_path = tmp_path / "terrain.cog.tif"
    transform = from_origin(139.0, 36.0, 0.01, 0.01)
    data = np.array([[10.0, 20.0], [30.0, -9999.0]], dtype="float32")

    with rasterio.open(
        source_path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)

    convert_fabdem_tile_to_ellipsoid_cog(
        source_path,
        output_path,
        geoid_provider=ConstantGeoidProvider(5.0),
    )

    with rasterio.open(output_path) as ds:
        assert str(ds.crs) == "EPSG:4326"
        assert ds.descriptions[0] == "terrain_h_ellipsoid_m"
        assert ds.tags()["vertical_datum"] == "WGS84_ELLIPSOID"
        assert ds.tags()["source"] == "FABDEM"
        assert ds.tags()["source_vertical_datum"] == "EGM2008"
        converted = ds.read(1)

    assert converted[0, 0] == pytest.approx(15.0)
    assert converted[0, 1] == pytest.approx(25.0)
    assert converted[1, 0] == pytest.approx(35.0)
    assert converted[1, 1] == pytest.approx(-9999.0)


def test_buildings_geoparquet_fields_and_surface_semantics(tmp_path) -> None:
    np = pytest.importorskip("numpy")
    gpd = pytest.importorskip("geopandas")
    rasterio = pytest.importorskip("rasterio")
    pytest.importorskip("pyarrow")
    from rasterio.transform import from_origin
    from shapely.geometry import Polygon

    from lightbluesky_map.buildings import build_buildings_geodataframe
    from lightbluesky_map.dataset import open_dataset
    from lightbluesky_map.terrain import write_terrain_cog

    dataset_root = create_dataset_folder(
        tmp_path / "global_wgs84_ellipsoid_3d_map",
        created_at="2026-05-31T00:00:00Z",
    )
    terrain_path = dataset_root / "terrain" / "fixture.cog.tif"
    transform = from_origin(0.0, 1.0, 0.5, 0.5)
    terrain = np.array([[100.0, 102.0], [104.0, 106.0]], dtype="float32")
    write_terrain_cog(terrain_path, terrain, transform=transform, nodata=None)

    source = gpd.GeoDataFrame(
        {
            "id": ["b1", "b2"],
            "height": [10.0, None],
            "num_floors": [None, None],
            "geometry": [
                Polygon([(0.05, 0.55), (0.45, 0.55), (0.45, 0.95), (0.05, 0.95)]),
                Polygon([(0.55, 0.55), (0.95, 0.55), (0.95, 0.95), (0.55, 0.95)]),
            ],
        },
        geometry="geometry",
        crs="EPSG:4326",
    )
    source_path = tmp_path / "overture_fixture.geoparquet"
    source.to_parquet(source_path, index=False)

    buildings = build_buildings_geodataframe(source_path, [terrain_path])
    buildings.to_parquet(dataset_root / "buildings" / "fixture.geoparquet", index=False)

    assert list(buildings.columns) == BUILDING_COLUMNS
    assert buildings.loc[0, "base_h_ellipsoid_m"] == pytest.approx(100.0)
    assert buildings.loc[0, "top_h_ellipsoid_m"] == pytest.approx(110.0)
    assert buildings.loc[1, "height_source"] == "missing"
    assert np.isnan(buildings.loc[1, "top_h_ellipsoid_m"])

    with open_dataset(dataset_root) as dataset:
        assert dataset.sample_terrain(0.25, 0.75) == pytest.approx(100.0)
        assert len(dataset.query_buildings(0.25, 0.75)) == 1
        assert dataset.sample_surface(0.25, 0.75) == pytest.approx(110.0)
        assert dataset.sample_surface(0.75, 0.75) == pytest.approx(102.0)
