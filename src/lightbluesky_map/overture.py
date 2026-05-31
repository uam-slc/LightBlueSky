"""Cloud access helpers for Overture Maps Buildings."""

from __future__ import annotations

from pathlib import Path

from .regions import BBox


DEFAULT_OVERTURE_RELEASE = "2026-05-20.0"


def overture_buildings_cloud_path(
    *,
    release: str = DEFAULT_OVERTURE_RELEASE,
    provider: str = "azure",
    include_parts: bool = False,
) -> str:
    """Return a DuckDB-readable cloud parquet glob for Overture Buildings."""

    building_type = "building_part" if include_parts else "building"
    if provider == "azure":
        return (
            "az://release/"
            f"{release}/theme=buildings/type={building_type}/*.parquet"
        )
    if provider == "s3":
        return (
            "s3://overturemaps-us-west-2/release/"
            f"{release}/theme=buildings/type={building_type}/*.parquet"
        )
    if provider == "https-azure":
        return (
            "https://overturemapswestus2.blob.core.windows.net/release/"
            f"{release}/theme=buildings/type={building_type}/*.parquet"
        )
    raise ValueError("provider must be one of: azure, s3, https-azure")


def overture_buildings_bbox_sql(
    *,
    cloud_path: str,
    bbox: BBox,
    output_path: str | Path,
) -> str:
    """Build the Overture bbox extraction SQL used by DuckDB."""

    min_lon, min_lat, max_lon, max_lat = bbox
    escaped_path = cloud_path.replace("'", "''")
    escaped_output = str(output_path).replace("\\", "/").replace("'", "''")
    return f"""
COPY (
    SELECT *
    FROM read_parquet('{escaped_path}', hive_partitioning = true)
    WHERE bbox.xmin <= {max_lon}
      AND bbox.xmax >= {min_lon}
      AND bbox.ymin <= {max_lat}
      AND bbox.ymax >= {min_lat}
) TO '{escaped_output}' (FORMAT PARQUET);
""".strip()


def extract_overture_buildings_for_bbox(
    output_path: str | Path,
    *,
    bbox: BBox,
    release: str = DEFAULT_OVERTURE_RELEASE,
    provider: str = "azure",
    include_parts: bool = False,
) -> Path:
    """Extract Overture Buildings from cloud storage for a lon/lat bbox."""

    try:
        import duckdb
    except ImportError as exc:
        raise ImportError(
            "duckdb is required for Overture cloud extraction. Install the "
            "project dependencies first."
        ) from exc

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cloud_path = overture_buildings_cloud_path(
        release=release,
        provider=provider,
        include_parts=include_parts,
    )
    sql = overture_buildings_bbox_sql(
        cloud_path=cloud_path,
        bbox=bbox,
        output_path=output_path,
    )

    with duckdb.connect() as connection:
        connection.execute("INSTALL spatial;")
        connection.execute("LOAD spatial;")
        connection.execute("INSTALL httpfs;")
        connection.execute("LOAD httpfs;")
        if provider == "azure":
            connection.execute("INSTALL azure;")
            connection.execute("LOAD azure;")
            connection.execute("SET azure_transport_option_type = 'curl';")
        connection.execute(sql)

    return output_path
