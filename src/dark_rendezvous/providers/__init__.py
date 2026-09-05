"""External AIS and vessel-identity providers."""

from .gfw import GFW_GAP_ENDPOINT_COLUMNS, GfwClient, normalize_gap_endpoints
from .noaa import NoaaMarineCadastreProvider

__all__ = [
    "GFW_GAP_ENDPOINT_COLUMNS",
    "GfwClient",
    "NoaaMarineCadastreProvider",
    "normalize_gap_endpoints",
]
