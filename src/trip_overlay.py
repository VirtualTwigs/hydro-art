"""Trip overlay: GPX/KML path parsing and SVG overlay.

Pure and offline-testable — no GDAL, no network. Uses stdlib XML parsing.
Coordinates are (lat, lon) tuples in WGS84. CRS reprojection to EPSG:5070
happens at render time (lazy-imported, not at module load).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

__all__ = [
    "TripOverlayError",
    "overlay_path_on_svg",
    "parse_gpx",
    "parse_kml",
    "trip_surcharge",
    "validate_trip_order",
]


class TripOverlayError(Exception):
    """Raised for invalid trip overlay input."""


def parse_gpx(xml_str: str) -> list[tuple[float, float]]:
    """Parse a GPX string and extract track coordinates.

    Returns:
        List of ``(lat, lon)`` tuples.

    Raises:
        TripOverlayError: If the XML is malformed or contains no track points.
    """
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as exc:
        raise TripOverlayError(f"Invalid GPX XML: {exc}") from exc

    coords: list[tuple[float, float]] = []

    for trkpt in root.iter("{http://www.topografix.com/GPX/1/1}trkpt"):
        lat = trkpt.get("lat")
        lon = trkpt.get("lon")
        if lat is not None and lon is not None:
            coords.append((float(lat), float(lon)))

    # Also try without namespace (some GPX files omit it)
    if not coords:
        for trkpt in root.iter("trkpt"):
            lat = trkpt.get("lat")
            lon = trkpt.get("lon")
            if lat is not None and lon is not None:
                coords.append((float(lat), float(lon)))

    if not coords:
        raise TripOverlayError("No track points found in GPX.")

    return coords


def parse_kml(xml_str: str) -> list[tuple[float, float]]:
    """Parse a KML string and extract LineString coordinates.

    KML coordinate format is ``lon,lat,ele`` (space-separated tuples).

    Returns:
        List of ``(lat, lon)`` tuples.

    Raises:
        TripOverlayError: If the XML is malformed or contains no coordinates.
    """
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as exc:
        raise TripOverlayError(f"Invalid KML XML: {exc}") from exc

    coords: list[tuple[float, float]] = []

    for elem in root.iter("{http://www.opengis.net/kml/2.2}coordinates"):
        text = (elem.text or "").strip()
        for triple in text.split():
            parts = triple.split(",")
            if len(parts) >= 2:
                lon, lat = float(parts[0]), float(parts[1])
                coords.append((lat, lon))

    # Also try without namespace
    if not coords:
        for elem in root.iter("coordinates"):
            text = (elem.text or "").strip()
            for triple in text.split():
                parts = triple.split(",")
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    coords.append((lat, lon))

    if not coords:
        raise TripOverlayError("No coordinates found in KML.")

    return coords


def overlay_path_on_svg(
    svg_content: str,
    coords: list[tuple[float, float]],
    *,
    stroke: str = "#ff6600",
    stroke_width: float = 3.0,
    opacity: float = 0.8,
) -> str:
    """Add a trip path polyline to an SVG string.

    Coordinates are mapped linearly into the SVG viewbox. For production use,
    coordinates should be reprojected to match the SVG's CRS first.

    Args:
        svg_content: Source SVG markup.
        coords: List of ``(lat, lon)`` tuples.
        stroke: Path stroke color.
        stroke_width: Path stroke width.
        opacity: Path opacity.

    Returns:
        SVG markup with trip path polyline added.
    """
    if not coords:
        return svg_content

    # Simple linear mapping of lat/lon to SVG pixel space.
    # In production, coords would be reprojected to EPSG:5070 first.
    import re
    width = 500
    height = 500
    w_match = re.search(r'width="(\d+)"', svg_content)
    h_match = re.search(r'height="(\d+)"', svg_content)
    if w_match:
        width = int(w_match.group(1))
    if h_match:
        height = int(h_match.group(1))

    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)

    # Avoid division by zero
    lat_range = lat_max - lat_min or 1.0
    lon_range = lon_max - lon_min or 1.0

    margin = 0.1  # 10% margin
    ew = width * (1 - 2 * margin)
    eh = height * (1 - 2 * margin)

    points = []
    for lat, lon in coords:
        x = margin * width + ((lon - lon_min) / lon_range) * ew
        y = margin * height + ((lat_max - lat) / lat_range) * eh  # flip Y
        points.append(f"{x:.1f},{y:.1f}")

    points_str = " ".join(points)
    polyline = (
        f'<polyline points="{points_str}" '
        f'fill="none" stroke="{stroke}" stroke-width="{stroke_width}" '
        f'stroke-opacity="{opacity}" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    return svg_content.replace("</svg>", f"{polyline}</svg>")


def trip_surcharge(base_cents: int) -> int:
    """Calculate the 50% trip memorial surcharge.

    Args:
        base_cents: Base price in cents.

    Returns:
        Total price in cents (base * 1.5).
    """
    return int(base_cents * 1.5)


def validate_trip_order(*, is_trip: bool, file_content: str | None) -> None:
    """Validate that a trip order includes a GPX/KML file.

    Raises:
        TripOverlayError: If ``is_trip`` is True but no file content is provided.
    """
    if is_trip and not file_content:
        raise TripOverlayError("Trip memorial orders require a GPX or KML file upload.")
