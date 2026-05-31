"""EGM2008 geoid separation providers.

FABDEM heights are treated as EGM2008 orthometric heights in this package.
The conversion to WGS84 ellipsoid height is:

    h_ellipsoid_m = H_fabdem_m + N_egm2008_m
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import shutil
import subprocess
from typing import Iterable, Protocol, runtime_checkable


class GeoidModelUnavailable(RuntimeError):
    """Raised when no configured geoid backend can evaluate EGM2008."""


@runtime_checkable
class GeoidProvider(Protocol):
    """Provider for geoid separation values in meters."""

    def separation(self, lat_deg: float, lon_deg: float) -> float:
        """Return N_egm2008_m at WGS84 latitude and longitude."""


_FLOAT_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


@dataclass(frozen=True)
class EGM2008GeoidProvider:
    """GeographicLib GeoidEval-backed EGM2008 provider.

    The Python ``geographiclib`` package does not consistently ship geoid grid
    interpolation APIs. This provider therefore uses the GeographicLib
    ``GeoidEval`` executable when available. Install the EGM2008 grid data that
    matches ``model_name`` before using it for production conversion.
    """

    model_name: str = "egm2008-1"
    executable: str | None = None
    timeout_s: float = 10.0

    def separation(self, lat_deg: float, lon_deg: float) -> float:
        exe = self.executable or shutil.which("GeoidEval")
        if exe is None:
            raise GeoidModelUnavailable(
                "GeographicLib GeoidEval was not found. Install GeographicLib "
                "with EGM2008 grid data or pass a custom GeoidProvider."
            )

        proc = subprocess.run(
            [exe, "-n", self.model_name],
            input=f"{float(lat_deg)} {float(lon_deg)}\n",
            capture_output=True,
            check=False,
            text=True,
            timeout=self.timeout_s,
        )
        if proc.returncode != 0:
            message = proc.stderr.strip() or proc.stdout.strip()
            raise GeoidModelUnavailable(
                f"GeoidEval failed for {lat_deg=}, {lon_deg=}: {message}"
            )

        match = _FLOAT_RE.search(proc.stdout)
        if match is None:
            raise GeoidModelUnavailable(
                f"Could not parse GeoidEval output: {proc.stdout!r}"
            )
        return float(match.group(0))

    def separations(
        self, lat_deg: Iterable[float], lon_deg: Iterable[float]
    ) -> list[float]:
        """Return geoid separations for an iterable of points.

        This is intentionally simple and deterministic. A production runner can
        provide a vectorized provider with the same method for higher throughput.
        """

        return [
            self.separation(lat, lon) for lat, lon in zip(lat_deg, lon_deg, strict=True)
        ]


@dataclass(frozen=True)
class PyProjEGM2008GeoidProvider:
    """PROJ/pyproj EGM2008-compatible geoid provider.

    This transforms a zero EGM2008 orthometric height from the compound CRS
    ``EPSG:4326+3855`` to WGS84 ellipsoid height ``EPSG:4979``. The returned
    ellipsoid height is the geoid separation ``N_egm2008_m``.
    """

    network_enabled: bool = True

    def _transformer(self):
        try:
            from pyproj import Transformer, network
        except ImportError as exc:
            raise GeoidModelUnavailable(
                "pyproj is required for the PROJ EGM2008 geoid provider"
            ) from exc

        network.set_network_enabled(self.network_enabled)
        return Transformer.from_crs("EPSG:4326+3855", "EPSG:4979", always_xy=True)

    def separation(self, lat_deg: float, lon_deg: float) -> float:
        transformer = self._transformer()
        _, _, h_ellipsoid_m = transformer.transform(
            float(lon_deg), float(lat_deg), 0.0
        )
        return float(h_ellipsoid_m)

    def separations(
        self, lat_deg: Iterable[float], lon_deg: Iterable[float]
    ) -> list[float]:
        transformer = self._transformer()
        lon_values = list(lon_deg)
        lat_values = list(lat_deg)
        _, _, h_values = transformer.transform(lon_values, lat_values, [0.0] * len(lon_values))
        return [float(value) for value in h_values]


@dataclass(frozen=True)
class ConstantGeoidProvider:
    """Small deterministic provider used by tests and examples."""

    value_m: float

    def separation(self, lat_deg: float, lon_deg: float) -> float:
        return float(self.value_m)

    def separations(
        self, lat_deg: Iterable[float], lon_deg: Iterable[float]
    ) -> list[float]:
        return [float(self.value_m) for _ in zip(lat_deg, lon_deg, strict=True)]


_DEFAULT_PROVIDER: GeoidProvider | None = None


def get_default_geoid_provider() -> GeoidProvider:
    global _DEFAULT_PROVIDER
    if _DEFAULT_PROVIDER is None:
        if shutil.which("GeoidEval") is not None:
            _DEFAULT_PROVIDER = EGM2008GeoidProvider()
        else:
            _DEFAULT_PROVIDER = PyProjEGM2008GeoidProvider()
    return _DEFAULT_PROVIDER


def get_geoid_separation(lat_deg: float, lon_deg: float) -> float:
    """Return EGM2008 geoid separation in meters for a WGS84 lon/lat point."""

    return get_default_geoid_provider().separation(lat_deg, lon_deg)
