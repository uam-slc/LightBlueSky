# Overture Buildings Cloud Access

This dataset uses Overture Maps Buildings as the building footprint and height source.

The final aligned building output belongs in:

```text
global_wgs84_ellipsoid_3d_map/buildings/<building_partition_id>.geoparquet
```

Do not put raw Overture cache files in `global_wgs84_ellipsoid_3d_map/buildings/` unless they have already been aligned to this dataset schema. Raw Overture files are source inputs; the final `buildings/` directory stores records with `base_h_ellipsoid_m` and `top_h_ellipsoid_m`.

## Beijing-Tianjin-Hebei Bbox

The default regional bbox is:

```text
min_lon = 113.0
min_lat = 36.0
max_lon = 120.0
max_lat = 42.8
```

## Cloud Input

The default Overture release is:

```text
2026-05-20.0
```

The recommended anonymous cloud path is HTTPS Azure Blob. The builder lists parquet objects from the public container and passes the resulting URL list to DuckDB:

```text
https://overturemapswestus2.blob.core.windows.net/release/2026-05-20.0/theme=buildings/type=building/*.parquet
```

The `az://` form is also supported by the code, but DuckDB may require Azure credentials for it in some environments:

```text
az://release/2026-05-20.0/theme=buildings/type=building/*.parquet
```

Equivalent S3 path:

```text
s3://overturemaps-us-west-2/release/2026-05-20.0/theme=buildings/type=building/*.parquet
```

## Download Regional Overture Cache Only

This creates a local raw Overture regional cache. It does not create the final aligned dataset because terrain sampling still requires converted FABDEM COG files.

```bash
python -m lightbluesky_map.build_region --region bth --download-overture-only --overture-raw-output data/overture/beijing-tianjin-hebei_overture_buildings_raw.geoparquet
```

## Build With Cloud Overture Input

This mode reads Overture Buildings from cloud storage, writes a raw regional cache under `data/work/`, then aligns buildings against terrain COG files.

```bash
python -m lightbluesky_map.build_region --region bth --fabdem-raster path/to/fabdem_tile_1.tif --fabdem-raster path/to/fabdem_tile_2.tif --output global_wgs84_ellipsoid_3d_map
```

## Build With Local Overture Input

This mode skips cloud extraction and uses a local raw Overture regional GeoParquet file.

```bash
python -m lightbluesky_map.build_region --region bth --fabdem-raster path/to/fabdem_tile_1.tif --fabdem-raster path/to/fabdem_tile_2.tif --overture-buildings-local data/overture/beijing-tianjin-hebei_overture_buildings_raw.geoparquet --output global_wgs84_ellipsoid_3d_map
```

## Alignment Rule

Overture provides WGS84 building footprints and height attributes. The builder samples `base_h_ellipsoid_m` from the converted FABDEM terrain COG and computes:

```text
top_h_ellipsoid_m = base_h_ellipsoid_m + height_m
```

The final output is written to `global_wgs84_ellipsoid_3d_map/buildings/`.
