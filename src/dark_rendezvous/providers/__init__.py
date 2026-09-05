"""External AIS and vessel-identity providers."""

from .gfw import GFW_GAP_ENDPOINT_COLUMNS, GfwClient, normalize_gap_endpoints
from .gfw_presence import (
    GFW_PRESENCE_COLUMNS,
    PRESENCE_POSITION_SEMANTICS,
    PRESENCE_SOURCE,
    normalize_presence_report,
)
from .gfw_tracks import TRACK_SOURCE, normalize_track_lines
from .noaa import NoaaMarineCadastreProvider

__all__ = [
    "GFW_GAP_ENDPOINT_COLUMNS",
    "GFW_PRESENCE_COLUMNS",
    "GfwClient",
    "NoaaMarineCadastreProvider",
    "PRESENCE_POSITION_SEMANTICS",
    "PRESENCE_SOURCE",
    "TRACK_SOURCE",
    "normalize_gap_endpoints",
    "normalize_presence_report",
    "normalize_track_lines",
]
