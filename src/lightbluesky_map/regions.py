"""Named regional build definitions."""

from __future__ import annotations

from dataclasses import dataclass


BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class RegionSpec:
    """A lon/lat regional build target."""

    name: str
    title: str
    bbox: BBox
    fabdem_10x10_tile_ids: tuple[str, ...]

    @property
    def min_lon(self) -> float:
        return self.bbox[0]

    @property
    def min_lat(self) -> float:
        return self.bbox[1]

    @property
    def max_lon(self) -> float:
        return self.bbox[2]

    @property
    def max_lat(self) -> float:
        return self.bbox[3]


BEIJING_TIANJIN_HEBEI = RegionSpec(
    name="beijing-tianjin-hebei",
    title="Beijing, Tianjin, and Hebei",
    bbox=(113.0, 36.0, 120.0, 42.8),
    fabdem_10x10_tile_ids=(
        "N30E110-N40E120",
        "N40E110-N50E120",
    ),
)


REGIONS = {
    "bth": BEIJING_TIANJIN_HEBEI,
    "beijing-tianjin-hebei": BEIJING_TIANJIN_HEBEI,
    "jing-jin-ji": BEIJING_TIANJIN_HEBEI,
}


def get_region(name: str) -> RegionSpec:
    try:
        return REGIONS[name.lower()]
    except KeyError as exc:
        available = ", ".join(sorted(REGIONS))
        raise ValueError(f"Unknown region {name!r}. Available regions: {available}") from exc


def parse_bbox(value: str) -> BBox:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be min_lon,min_lat,max_lon,max_lat")
    min_lon, min_lat, max_lon, max_lat = parts
    if min_lon >= max_lon or min_lat >= max_lat:
        raise ValueError("bbox min values must be less than max values")
    return min_lon, min_lat, max_lon, max_lat
