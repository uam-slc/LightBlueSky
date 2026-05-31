"""Regional dataset build CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from .buildings import convert_overture_buildings_to_geoparquet
from .dataset import DATASET_NAME, create_dataset_folder
from .geoid import EGM2008GeoidProvider
from .overture import DEFAULT_OVERTURE_RELEASE, extract_overture_buildings_for_bbox
from .regions import RegionSpec, get_region, parse_bbox
from .terrain import convert_fabdem_tile_to_ellipsoid_cog


def build_region_dataset(
    *,
    region: RegionSpec,
    fabdem_rasters: list[str | Path],
    output_dir: str | Path = DATASET_NAME,
    work_dir: str | Path = "data/work",
    overture_release: str = DEFAULT_OVERTURE_RELEASE,
    overture_provider: str = "azure",
    floor_height_m: float = 3.0,
    include_building_parts: bool = False,
) -> Path:
    """Build one regional dataset folder from FABDEM rasters and Overture cloud."""

    if not fabdem_rasters:
        required = ", ".join(region.fabdem_10x10_tile_ids)
        raise ValueError(
            "At least one FABDEM raster is required. For this region, start "
            f"from these 10x10 FABDEM packages: {required}."
        )

    output_root = create_dataset_folder(
        output_dir,
        dataset_scope="regional",
        region_name=region.name,
        region_title=region.title,
        region_bbox_lon_lat=list(region.bbox),
        floor_height_m=floor_height_m,
        terrain_tile_scheme=(
            f"{region.name} clipped/source FABDEM rasters, emitted as "
            "<terrain_tile_id>.cog.tif"
        ),
        building_partition_scheme=(
            f"{region.name} Overture bbox partition, emitted as "
            "<building_partition_id>.geoparquet"
        ),
        generation_parameters={
            "region_name": region.name,
            "region_title": region.title,
            "bbox_lon_lat": list(region.bbox),
            "required_fabdem_10x10_tile_ids": list(region.fabdem_10x10_tile_ids),
            "overture_release": overture_release,
            "overture_provider": overture_provider,
            "terrain_height_formula": (
                "terrain_h_ellipsoid_m = H_fabdem_m + N_egm2008_m"
            ),
            "building_top_formula": (
                "top_h_ellipsoid_m = base_h_ellipsoid_m + height_m"
            ),
            "terrain_sample_method_default": "footprint_points_median",
        },
    )
    work_root = Path(work_dir)
    work_root.mkdir(parents=True, exist_ok=True)

    geoid_provider = EGM2008GeoidProvider()
    terrain_paths = []
    for fabdem_raster in fabdem_rasters:
        source = Path(fabdem_raster)
        terrain_id = f"{region.name}_{source.stem}.cog.tif"
        terrain_path = output_root / "terrain" / terrain_id
        convert_fabdem_tile_to_ellipsoid_cog(
            source,
            terrain_path,
            geoid_provider=geoid_provider,
        )
        terrain_paths.append(terrain_path)

    raw_overture_path = work_root / f"{region.name}_overture_buildings_raw.geoparquet"
    extract_overture_buildings_for_bbox(
        raw_overture_path,
        bbox=region.bbox,
        release=overture_release,
        provider=overture_provider,
        include_parts=include_building_parts,
    )

    convert_overture_buildings_to_geoparquet(
        raw_overture_path,
        terrain_paths,
        output_root / "buildings" / f"{region.name}.geoparquet",
        floor_height_m=floor_height_m,
    )
    return output_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a regional WGS84 ellipsoid-height 3D map dataset."
    )
    parser.add_argument("--region", default="bth", help="Named region. Default: bth")
    parser.add_argument(
        "--bbox",
        help="Override region bbox as min_lon,min_lat,max_lon,max_lat.",
    )
    parser.add_argument(
        "--fabdem-raster",
        action="append",
        default=[],
        help="Input FABDEM raster path. Repeat for multiple source rasters.",
    )
    parser.add_argument("--output", default=DATASET_NAME)
    parser.add_argument("--work-dir", default="data/work")
    parser.add_argument("--overture-release", default=DEFAULT_OVERTURE_RELEASE)
    parser.add_argument(
        "--overture-provider",
        default="azure",
        choices=("azure", "s3", "https-azure"),
    )
    parser.add_argument("--floor-height-m", type=float, default=3.0)
    parser.add_argument("--include-building-parts", action="store_true")
    parser.add_argument(
        "--print-required-fabdem-tiles",
        action="store_true",
        help="Print required FABDEM 10x10 package IDs and exit.",
    )
    args = parser.parse_args(argv)

    region = get_region(args.region)
    if args.bbox:
        region = RegionSpec(
            name=region.name,
            title=region.title,
            bbox=parse_bbox(args.bbox),
            fabdem_10x10_tile_ids=region.fabdem_10x10_tile_ids,
        )

    if args.print_required_fabdem_tiles:
        for tile_id in region.fabdem_10x10_tile_ids:
            print(tile_id)
        return 0

    build_region_dataset(
        region=region,
        fabdem_rasters=args.fabdem_raster,
        output_dir=args.output,
        work_dir=args.work_dir,
        overture_release=args.overture_release,
        overture_provider=args.overture_provider,
        floor_height_m=args.floor_height_m,
        include_building_parts=args.include_building_parts,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
