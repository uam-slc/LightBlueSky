# global_wgs84_ellipsoid_3d_map

This folder is the WGS84 ellipsoid-height three-dimensional map dataset contract for low-altitude traffic management simulation. The same schema supports global datasets and regional cuts such as Beijing-Tianjin-Hebei; check `manifest.json` for the actual `dataset_scope` and optional region fields. It stores terrain and building surfaces in one coordinate and height convention:

- lon: WGS84 longitude.
- lat: WGS84 latitude.
- h_ellipsoid_m: WGS84 ellipsoid height in meters.

## Files

- `README.md`: dataset semantics and field contract.
- `manifest.json`: machine-readable dataset metadata.
- `terrain/<terrain_tile_id>.cog.tif`: terrain Cloud Optimized GeoTIFF tiles.
- `buildings/<building_partition_id>.geoparquet`: building footprint and height partitions.
- `OVERTURE_CLOUD.md`: cloud and local Overture Buildings input instructions.

## Generated Beijing-Tianjin-Hebei Dataset

This checkout contains a generated Beijing-Tianjin-Hebei regional cut:

- Region bbox: `min_lon=113.0`, `min_lat=36.0`, `max_lon=120.0`, `max_lat=42.8`.
- Terrain output: 48 COG files under `terrain/`, total 2,659,119,611 bytes.
- Building output: `buildings/beijing-tianjin-hebei.geoparquet`, 34,092,933 records, 3,155,437,026 bytes.
- Buildings with sampled `base_h_ellipsoid_m`: 34,090,682.
- Buildings with usable `height_m` and `top_h_ellipsoid_m`: 28,456.
- Building base sampling method for this generated cut: `bbox_center_pixel`.

The FABDEM package `N30E110-N40E120_FABDEM_V1-2.zip` does not contain `N38E119_FABDEM_V1-2.tif`; terrain coverage therefore has that source tile gap. The generated buildings layer still retains affected footprints, but records without terrain under the bbox center have null `base_h_ellipsoid_m` and null `top_h_ellipsoid_m`.

## Terrain Data

Each terrain COG uses CRS `EPSG:4326`, coordinate order `lon_lat`, and band name `terrain_h_ellipsoid_m`. Pixel values are WGS84 ellipsoid heights in meters:

```text
terrain_h_ellipsoid_m = H_fabdem_m + N_egm2008_m
```

`H_fabdem_m` is the FABDEM source elevation treated as an EGM2008 orthometric height. `N_egm2008_m` is the EGM2008 geoid separation from GeographicLib or a compatible PROJ/pyproj interpolator. NoData values are preserved.

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

## Beijing-Tianjin-Hebei Regional Build

The repository includes a regional build entrypoint for Beijing, Tianjin, and Hebei. It uses Overture Buildings directly from cloud GeoParquet and local FABDEM raster inputs:

```bash
python -m lightbluesky_map.build_region --region bth --print-required-fabdem-tiles
```

Expected FABDEM 10x10 source packages for this bbox are:

- `N30E110-N40E120`
- `N40E110-N50E120`

After the relevant FABDEM rasters have been extracted or prepared locally, run:

```bash
python -m lightbluesky_map.build_region --region bth --fabdem-raster path/to/fabdem_tile_1.tif --fabdem-raster path/to/fabdem_tile_2.tif --output global_wgs84_ellipsoid_3d_map
```

The build converts FABDEM to terrain COG files first, then extracts Overture Buildings by bbox from the configured cloud release, samples `base_h_ellipsoid_m` from the terrain COG files, and writes aligned building GeoParquet output.

## Format Rationale

Terrain uses Cloud Optimized GeoTIFF because COG supports global tiling, windowed reads, rasterio/GDAL access, georeferencing, metadata, and NoData preservation.

Buildings use GeoParquet because it supports large vector partitions, geometry and attributes, and direct access from geopandas, duckdb, and pyarrow.

## Python Reading Examples

Use the helper API for simple point queries:

```python
from lightbluesky_map import open_dataset

lon, lat = 116.4074, 39.9042

with open_dataset("global_wgs84_ellipsoid_3d_map") as dataset:
    terrain_h = dataset.sample_terrain(lon, lat)
    buildings = dataset.query_buildings(lon, lat)
    surface_h = dataset.sample_surface(lon, lat)

print("terrain_h_ellipsoid_m:", terrain_h)
print(buildings[[
    "id",
    "height_m",
    "base_h_ellipsoid_m",
    "top_h_ellipsoid_m",
    "height_source",
    "height_confidence",
]])
print("surface_h_ellipsoid_m:", surface_h)
```

Read terrain directly with rasterio:

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

For this large generated building partition, prefer DuckDB for filtering instead of loading all 34 million records into GeoPandas:

```python
import duckdb

lon, lat = 116.4074, 39.9042

con = duckdb.connect()
con.execute("INSTALL spatial;")
con.execute("LOAD spatial;")

rows = con.execute(
    '''
    SELECT
        id,
        height_m,
        base_h_ellipsoid_m,
        top_h_ellipsoid_m,
        height_source,
        height_confidence
    FROM read_parquet('global_wgs84_ellipsoid_3d_map/buildings/beijing-tianjin-hebei.geoparquet')
    WHERE ST_Covers(geometry, ST_Point(?, ?))
    ''',
    [lon, lat],
).fetchdf()

print(rows)
```
