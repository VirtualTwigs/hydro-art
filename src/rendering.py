"""Layered SVG rendering (PRD sections 17-19).

Turns the colored river network into a single, editable SVG document: every
segment becomes a round-capped, round-joined vector path, grouped by watershed
into ``<g>`` layers on a solid background. Rendering is a pure, deterministic
computation over shapely geometries and plain color/watershed dicts, so it is
fully unit-testable with hand-built lines (no GDAL, no browser, no real data).

The SVG is serialized by hand over the stdlib (no external SVG library) so that
coordinate precision and element ordering are fully under our control, giving
byte-identical output from identical inputs (the reproducibility goal of a later
roadmap item).

Coordinate note: projected northing increases upward while SVG's y-axis
increases downward, so coordinates are flipped to ``max_y - y`` (and translated
by ``-min_x``) to keep north up in the rendered image.
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator, Mapping

__all__ = [
    "bounds",
    "format_number",
    "transform_coords",
    "path_d",
    "render_svg",
    "stream_order_widths",
]

Coord = tuple[float, float]

#: Decimals used when formatting stroke widths (independent of coordinate
#: precision, which callers may tune for file size).
_WIDTH_PRECISION = 3

#: Color used for a segment that has no assigned watershed color.
DEFAULT_FALLBACK_COLOR = "#ffffff"


def _iter_line_parts(geom: Any) -> Iterator[Any]:
    """Yield the LineString parts of a (possibly multi) line geometry."""
    if geom is None or geom.is_empty:
        return
    kind = geom.geom_type
    if kind == "LineString":
        yield geom
    elif kind == "MultiLineString":
        for part in geom.geoms:
            if not part.is_empty:
                yield part


def bounds(geometries: Iterable[Any]) -> tuple[float, float, float, float]:
    """Return ``(min_x, min_y, max_x, max_y)`` over all line coordinates.

    Empty input yields a well-defined zero box ``(0, 0, 0, 0)`` so callers never
    have to special-case an undefined bounding box.
    """
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    seen = False
    for geom in geometries:
        for part in _iter_line_parts(geom):
            for x, y in part.coords:
                seen = True
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
    if not seen:
        return (0.0, 0.0, 0.0, 0.0)
    return (min_x, min_y, max_x, max_y)


def format_number(value: float, precision: int) -> str:
    """Format ``value`` to ``precision`` decimals, deterministically.

    Trailing zeros and any trailing decimal point are stripped, and negative
    zero is normalized to ``"0"`` so equal magnitudes never diverge on sign.
    """
    text = f"{value:.{precision}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("-0", "") or text == "-":
        text = "0"
    return text


def transform_coords(
    coords: Iterable[Coord], min_x: float, max_y: float, precision: int
) -> list[tuple[str, str]]:
    """Translate to a ``0,0`` origin and flip Y, returning formatted strings.

    Each ``(x, y)`` becomes ``(x - min_x, max_y - y)`` (north stays up), then is
    formatted via :func:`format_number`.
    """
    return [
        (
            format_number(x - min_x, precision),
            format_number(max_y - y, precision),
        )
        for x, y in coords
    ]


def path_d(geom: Any, min_x: float, max_y: float, precision: int) -> str:
    """Build an SVG path ``d`` string for a (possibly multi-part) line geometry.

    Each line part contributes an ``M x,y`` move followed by ``L x,y`` segments;
    multi-part geometries yield multiple sub-paths within one ``d`` string.
    """
    subpaths: list[str] = []
    for part in _iter_line_parts(geom):
        points = transform_coords(part.coords, min_x, max_y, precision)
        if not points:
            continue
        commands = [f"M {points[0][0]},{points[0][1]}"]
        commands += [f"L {x},{y}" for x, y in points[1:]]
        subpaths.append(" ".join(commands))
    return " ".join(subpaths)


def _path_element(
    segment_id: int,
    geom: Any,
    min_x: float,
    max_y: float,
    precision: int,
    stroke: str | None,
    stroke_widths: Mapping[int, float] | None,
) -> str:
    """Serialize one ``<path>`` element (stroke color/width optional)."""
    attrs = [f'd="{path_d(geom, min_x, max_y, precision)}"']
    if stroke is not None:
        attrs.append(f'stroke="{stroke}"')
    if stroke_widths is not None and segment_id in stroke_widths:
        width = format_number(stroke_widths[segment_id], _WIDTH_PRECISION)
        attrs.append(f'stroke-width="{width}"')
    return "    <path " + " ".join(attrs) + "/>"


def render_svg(
    geometries: Mapping[int, Any],
    segment_colors: Mapping[int, str],
    watersheds: Mapping[str, set[int]],
    *,
    background: str = "#000000",
    line_width: float = 0.35,
    precision: int = 3,
    stroke_widths: Mapping[int, float] | None = None,
    fallback_color: str = DEFAULT_FALLBACK_COLOR,
) -> str:
    """Render the colored river network as a single layered SVG document.

    Structure follows PRD section 18::

        <svg><defs/><g id="background"/><g id="watershed_<code>"/>…</svg>

    Every segment is a round-capped/round-joined ``<path>`` (styling inherited
    from the root); segments are grouped into ``<g>`` layers by watershed, each
    group carrying its watershed's color as ``stroke``. Segments not covered by
    any watershed are emitted last in a ``rivers_unassigned`` group. Coordinates
    flip Y (north up) into a ``0,0``-origin ``viewBox``.

    The output is deterministic: watershed groups are emitted in sorted code
    order, segments in sorted id order, coordinates at fixed ``precision``, and
    attribute order is stable — identical inputs yield an identical string.

    Args:
        geometries: Mapping of ``segment_id`` -> shapely line geometry.
        segment_colors: Mapping of ``segment_id`` -> hex color.
        watersheds: Mapping of HUC code -> set of ``segment_id`` (grouping).
        background: Background fill color.
        line_width: Base (uniform) stroke width.
        precision: Coordinate decimal precision.
        stroke_widths: Optional per-segment stroke widths (enables width
            scaling); omitted segments inherit ``line_width``.
        fallback_color: Stroke color for a segment lacking an assigned color.

    Returns:
        The SVG document as a string (trailing newline included).
    """
    min_x, min_y, max_x, max_y = bounds(geometries.values())
    width = format_number(max_x - min_x, precision)
    height = format_number(max_y - min_y, precision)
    base_width = format_number(line_width, _WIDTH_PRECISION)

    lines: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" width="{width}px" height="{height}px" '
        'fill="none" stroke-linecap="round" stroke-linejoin="round" '
        f'stroke-width="{base_width}">'
    )
    lines.append("  <defs/>")
    lines.append('  <g id="background">')
    lines.append(
        f'    <rect x="0" y="0" width="{width}" height="{height}" fill="{background}"/>'
    )
    lines.append("  </g>")

    grouped: set[int] = set().union(*watersheds.values()) if watersheds else set()

    for code in sorted(watersheds):
        segment_ids = sorted(sid for sid in watersheds[code] if sid in geometries)
        if not segment_ids:
            continue
        color = segment_colors.get(segment_ids[0], fallback_color)
        lines.append(f'  <g id="watershed_{code}" stroke="{color}">')
        for sid in segment_ids:
            lines.append(
                _path_element(
                    sid, geometries[sid], min_x, max_y, precision, None, stroke_widths
                )
            )
        lines.append("  </g>")

    unassigned = sorted(sid for sid in geometries if sid not in grouped)
    if unassigned:
        lines.append('  <g id="rivers_unassigned">')
        for sid in unassigned:
            color = segment_colors.get(sid, fallback_color)
            lines.append(
                _path_element(
                    sid, geometries[sid], min_x, max_y, precision, color, stroke_widths
                )
            )
        lines.append("  </g>")

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def stream_order_widths(
    stream_orders: Mapping[int, float],
    max_order: float,
    base_width: float,
    max_scale: float = 3.0,
) -> dict[int, float]:
    """Scale stroke width by stream order (optional width scaling, PRD section 17).

    Order 1 maps to ``base_width`` and ``max_order`` maps to
    ``base_width * max_scale``, interpolating linearly in between. Deterministic;
    a degenerate ``max_order <= 1`` yields a uniform ``base_width`` for all.

    Args:
        stream_orders: Mapping of ``segment_id`` -> stream order.
        max_order: The maximum stream order in the network.
        base_width: Stroke width at order 1.
        max_scale: Multiplier applied at ``max_order``.

    Returns:
        Mapping of ``segment_id`` -> stroke width.
    """
    top = base_width * max_scale
    if max_order <= 1:
        return {sid: base_width for sid in stream_orders}
    widths: dict[int, float] = {}
    for sid, order in stream_orders.items():
        if order <= 1:
            widths[sid] = base_width
        elif order >= max_order:
            widths[sid] = top
        else:
            frac = (order - 1) / (max_order - 1)
            widths[sid] = base_width + (top - base_width) * frac
    return widths
