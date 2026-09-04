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

import math
from typing import Any, Iterable, Iterator, Mapping

__all__ = [
    "bounds",
    "format_number",
    "transform_coords",
    "path_d",
    "polygon_path_d",
    "render_svg",
    "stream_order_widths",
    "flow_widths",
    "scaled_widths",
    "fixed_flow_span",
    "widths_on_span",
    "monthly_width_frames",
    "hypsometric_colors",
    "POINT_GLYPHS",
    "DEFAULT_POINT_STYLES",
    "DEFAULT_AREAL_STYLES",
    "HYDRO_STRUCTURE_GLYPHS",
    "DEFAULT_HYDRO_STRUCTURE_STYLES",
]

Coord = tuple[float, float]

#: Decimals used when formatting stroke widths (independent of coordinate
#: precision, which callers may tune for file size).
_WIDTH_PRECISION = 3

#: Color used for a segment that has no assigned watershed color.
DEFAULT_FALLBACK_COLOR = "#ffffff"

#: ``id`` of the Gaussian-blur glow filter injected into ``<defs>`` (blur mode).
GLOW_FILTER_ID = "hydro-glow"

#: Stroke opacity of a pure-vector glow halo (vector mode).
_HALO_OPACITY = 0.4


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
            for x, y, *_ in part.coords:
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
        for x, y, *_ in coords
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


def _iter_polygon_rings(geom: Any) -> Iterator[Any]:
    """Yield each ring (exterior then interiors) of a (multi)polygon geometry."""
    if geom is None or geom.is_empty:
        return
    kind = geom.geom_type
    if kind == "Polygon":
        yield geom.exterior.coords
        for interior in geom.interiors:
            yield interior.coords
    elif kind == "MultiPolygon":
        for part in geom.geoms:
            yield from _iter_polygon_rings(part)


def polygon_bounds(geometries: Iterable[Any]) -> tuple[float, float, float, float] | None:
    """Return ``(min_x, min_y, max_x, max_y)`` over polygon rings, or ``None``."""
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    seen = False
    for geom in geometries:
        for ring in _iter_polygon_rings(geom):
            for x, y, *_ in ring:
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
        return None
    return (min_x, min_y, max_x, max_y)


def polygon_path_d(geom: Any, min_x: float, max_y: float, precision: int) -> str:
    """Build an SVG path ``d`` for a (multi)polygon as closed ring subpaths.

    Each ring (exterior and every hole) becomes an ``M … L … Z`` closed
    subpath, so holes are preserved as independent outlines under ``fill=none``.
    Shapely rings repeat their first point to close; that duplicate is dropped
    in favor of the explicit ``Z``.
    """
    subpaths: list[str] = []
    for ring in _iter_polygon_rings(geom):
        points = transform_coords(ring, min_x, max_y, precision)
        if len(points) > 1 and points[0] == points[-1]:
            points = points[:-1]
        if len(points) < 2:
            continue
        commands = [f"M {points[0][0]},{points[0][1]}"]
        commands += [f"L {x},{y}" for x, y in points[1:]]
        commands.append("Z")
        subpaths.append(" ".join(commands))
    return " ".join(subpaths)


def _waterbody_lines(
    items: list[tuple],
    color: str,
    stroke_width: float,
    min_x: float,
    max_y: float,
    precision: int,
) -> list[str]:
    """Serialize the ``<g id="waterbodies">`` layer (no fill, one path per feature)."""
    width = format_number(stroke_width, _WIDTH_PRECISION)
    lines = [
        f'  <g id="waterbodies" fill="none" stroke="{color}" '
        f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">'
    ]
    for feature_id, geom, *rest in items:
        wb_class = rest[0] if rest else None
        group_attrs = [f'id="waterbody_{feature_id}"']
        if wb_class:
            group_attrs.append(f'data-class="{wb_class}"')
        lines.append(f"    <g {' '.join(group_attrs)}>")
        d = polygon_path_d(geom, min_x, max_y, precision)
        lines.append(f'      <path id="waterbody_{feature_id}_outline" d="{d}"/>')
        lines.append("    </g>")
    lines.append("  </g>")
    return lines


#: Default glyph shape per point family: springs=dots, waterfalls=chevrons,
#: rapids=tick/zigzag marks (spec Item 63; shapes echo ``tools/overlay_facilities``).
POINT_GLYPHS: dict[str, str] = {
    "spring": "dot",
    "waterfall": "chevron",
    "rapids": "tick",
}

#: Per-family point defaults (color/size/z-order). Callers (the config layer)
#: override these; kept here so ``render_svg`` is usable standalone in tests.
DEFAULT_POINT_STYLES: dict[str, dict[str, Any]] = {
    "spring": {"color": "#7fe3ff", "size": 1.5},
    "waterfall": {"color": "#eaf6ff", "size": 2.0},
    "rapids": {"color": "#bfefff", "size": 2.0},
}

#: Per-family areal defaults. ``fill`` is ``"hatch"`` (pattern), ``"solid"``
#: (with ``opacity``), or ``"none"`` (dashed outline). ``render_order`` places
#: the family ``"below"`` (default) or ``"above"`` the flowline/waterbody stack.
DEFAULT_AREAL_STYLES: dict[str, dict[str, Any]] = {
    "wetland": {"color": "#4fae86", "fill": "hatch", "render_order": "below"},
    "perennial_ice": {
        "color": "#dbeeff", "fill": "solid", "opacity": 0.35, "render_order": "below",
    },
    "playa": {"color": "#c9a86a", "fill": "none", "dash": "4,3", "render_order": "below"},
}


def _group_by_family(items: list[tuple]) -> dict[str, list[tuple]]:
    """Group ``(feature_id, geometry, family)`` items by family, preserving order."""
    groups: dict[str, list[tuple]] = {}
    for feature_id, geom, family in items:
        groups.setdefault(family, []).append((feature_id, geom))
    return groups


def _merge_style(defaults: dict[str, dict], family: str, styles: Mapping | None) -> dict:
    """Merge per-family default style with a caller override (override wins)."""
    merged = dict(defaults.get(family, {}))
    override = (styles or {}).get(family) if styles else None
    if override:
        merged.update(override)
    return merged


def _point_xy(geom: Any, min_x: float, max_y: float) -> tuple[float, float]:
    """Transform a point geometry to the flipped, origin-shifted SVG frame."""
    x, y = tuple(geom.coords[0])[:2]
    return (x - min_x, max_y - y)


def _point_bounds(items: list[tuple]) -> tuple[float, float, float, float] | None:
    """Return ``(min_x, min_y, max_x, max_y)`` over point geometries, or ``None``."""
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    seen = False
    for _feature_id, geom, _family in items:
        if geom is None or geom.is_empty:
            continue
        x, y = tuple(geom.coords[0])[:2]
        seen = True
        min_x, min_y = min(min_x, x), min(min_y, y)
        max_x, max_y = max(max_x, x), max(max_y, y)
    return (min_x, min_y, max_x, max_y) if seen else None


def _structure_bounds(
    items: list[tuple],
) -> tuple[float, float, float, float] | None:
    """Return ``(min_x, min_y, max_x, max_y)`` over mixed-geometry structures.

    Structures span point/line/polygon, so each geometry's own ``bounds`` box is
    unioned (a pure attribute read — no GIS import). Empty/None geometries skip.
    """
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    seen = False
    for _feature_id, geom, *_rest in items:
        if geom is None or getattr(geom, "is_empty", False):
            continue
        bx = getattr(geom, "bounds", None)
        if not bx:
            continue
        gx0, gy0, gx1, gy1 = bx
        seen = True
        min_x, min_y = min(min_x, gx0), min(min_y, gy0)
        max_x, max_y = max(max_x, gx1), max(max_y, gy1)
    return (min_x, min_y, max_x, max_y) if seen else None


def _glyph_element(
    shape: str, element_id: str, cx: float, cy: float, size: float, precision: int
) -> str:
    """Serialize one point glyph (``<circle>`` dot or stroked ``<path>``)."""
    def f(value: float) -> str:
        return format_number(value, precision)

    if shape == "dot":
        r = format_number(size, _WIDTH_PRECISION)
        return f'      <circle id="{element_id}" cx="{f(cx)}" cy="{f(cy)}" r="{r}"/>'
    if shape == "chevron":
        # An upward chevron "v" with its vertex at the point.
        d = f"M {f(cx - size)},{f(cy - size)} L {f(cx)},{f(cy)} L {f(cx + size)},{f(cy - size)}"
    else:  # tick / zigzag
        pts = [
            (cx - size, cy), (cx - size / 2, cy - size), (cx, cy),
            (cx + size / 2, cy - size), (cx + size, cy),
        ]
        d = f"M {f(pts[0][0])},{f(pts[0][1])} " + " ".join(
            f"L {f(x)},{f(y)}" for x, y in pts[1:]
        )
    return f'      <path id="{element_id}" d="{d}"/>'


def _point_features_lines(
    items: list[tuple],
    styles: Mapping | None,
    min_x: float,
    max_y: float,
    precision: int,
) -> list[str]:
    """Serialize ``<g id="point_features">`` with one child ``<g>`` per family."""
    groups = _group_by_family(items)
    lines = ['  <g id="point_features">']
    for family in sorted(groups):
        style = _merge_style(DEFAULT_POINT_STYLES, family, styles)
        color = style.get("color", DEFAULT_FALLBACK_COLOR)
        size = float(style.get("size", 1.5))
        shape = style.get("marker") or POINT_GLYPHS.get(family, "dot")
        if shape == "dot":
            group_attrs = f'id="point_{family}" fill="{color}"'
        else:
            sw = format_number(max(size * 0.4, 0.1), _WIDTH_PRECISION)
            group_attrs = (
                f'id="point_{family}" fill="none" stroke="{color}" '
                f'stroke-width="{sw}"'
            )
        lines.append(f"    <g {group_attrs}>")
        for feature_id, geom in groups[family]:
            cx, cy = _point_xy(geom, min_x, max_y)
            lines.append(
                _glyph_element(
                    shape, f"point_{family}_{feature_id}", cx, cy, size, precision
                )
            )
        lines.append("    </g>")
    lines.append("  </g>")
    return lines


def _areal_pattern_defs(items: list[tuple], styles: Mapping | None) -> list[str]:
    """Return ``<pattern>`` def lines for areal families using a hatch fill."""
    out: list[str] = []
    for family in sorted({family for _fid, _geom, family in items}):
        style = _merge_style(DEFAULT_AREAL_STYLES, family, styles)
        if style.get("fill") != "hatch":
            continue
        color = style.get("color", "#4fae86")
        out.extend(
            [
                f'    <pattern id="areal_{family}_hatch" width="4" height="4" '
                'patternUnits="userSpaceOnUse">',
                f'      <path d="M 0,4 L 4,0" stroke="{color}" '
                'stroke-width="0.5" fill="none"/>',
                "    </pattern>",
            ]
        )
    return out


def _areal_family_lines(
    family: str,
    feats: list[tuple],
    style: dict,
    min_x: float,
    max_y: float,
    precision: int,
) -> list[str]:
    """Serialize one ``<g id="areal_<family>">`` group with its differentiated fill."""
    fill_mode = style.get("fill", "none")
    color = style.get("color", "#888888")
    attrs = [f'id="areal_{family}"', f'data-class="{family}"']
    if fill_mode == "hatch":
        attrs.append(f'fill="url(#areal_{family}_hatch)"')
        attrs.append('fill-rule="evenodd"')
        attrs.append(f'stroke="{color}"')
    elif fill_mode == "solid":
        attrs.append(f'fill="{color}"')
        attrs.append(f'fill-opacity="{format_number(float(style.get("opacity", 1.0)), 2)}"')
        attrs.append('fill-rule="evenodd"')
    else:  # outline only
        attrs.append('fill="none"')
        attrs.append(f'stroke="{color}"')
        dash = style.get("dash")
        if dash:
            attrs.append(f'stroke-dasharray="{dash}"')
    lines = [f"  <g {' '.join(attrs)}>"]
    for feature_id, geom in feats:
        d = polygon_path_d(geom, min_x, max_y, precision)
        lines.append(f'    <path id="areal_{family}_{feature_id}" d="{d}"/>')
    lines.append("  </g>")
    return lines


def _areal_lines_for_order(
    groups: dict[str, list[tuple]],
    styles: Mapping | None,
    order: str,
    min_x: float,
    max_y: float,
    precision: int,
) -> list[str]:
    """Serialize the areal families whose ``render_order`` matches ``order``."""
    lines: list[str] = []
    for family in sorted(groups):
        style = _merge_style(DEFAULT_AREAL_STYLES, family, styles)
        if style.get("render_order", "below") != order:
            continue
        lines.extend(
            _areal_family_lines(family, groups[family], style, min_x, max_y, precision)
        )
    return lines


#: Default point-marker glyph per structure class (spec Item #67). Distinct
#: shapes so gaging stations, gate points, and area/point intakes read apart at
#: a glance (echoes the Epoch 15 point-glyph seam). Only structure classes that
#: can arrive as points appear here; a class absent from the table falls back to
#: ``"dot"``.
HYDRO_STRUCTURE_GLYPHS: dict[str, str] = {
    "gaging_station": "square",
    "water_intake_outflow": "diamond",
    "gate": "triangle",
}

#: Per-class default styling for engineered structures. Keyed on ``struct_class``;
#: the renderer refines by geometry kind (point → glyph, line → bar, polygon →
#: areal fill/outline). ``color`` is shared across kinds so a class reads
#: consistently; ``fill`` selects the polygon treatment (``"solid"`` with
#: ``opacity``, or ``"none"`` for a dashed outline via ``dash``). Callers (the
#: config layer) override these; kept here so ``render_svg`` is usable in tests.
DEFAULT_HYDRO_STRUCTURE_STYLES: dict[str, dict[str, Any]] = {
    "dam_weir": {"color": "#ff6b6b"},
    "gate": {"color": "#ffd166"},
    "gaging_station": {"color": "#f4a261"},
    "water_intake_outflow": {"color": "#e76f51"},
    "spillway": {"color": "#ff8fa3", "fill": "solid", "opacity": 0.35},
    "lock_chamber": {"color": "#ffb4a2", "fill": "solid", "opacity": 0.35},
    "canal_ditch": {"color": "#e5989b", "fill": "none", "dash": "4,3"},
}

#: Half-length (in SVG user units) of the perpendicular bar drawn for a line
#: structure — a bold tick reading *across* the channel it crosses.
_STRUCTURE_BAR_HALF = 3.0


def _structure_geometry_kind(geom: Any) -> str:
    """Classify a shapely geometry as ``"point"``/``"line"``/``"polygon"``."""
    gtype = getattr(geom, "geom_type", "")
    if gtype in ("Point", "MultiPoint"):
        return "point"
    if gtype in ("Polygon", "MultiPolygon"):
        return "polygon"
    return "line"


def _structure_bar_element(
    element_id: str,
    geom: Any,
    min_x: float,
    max_y: float,
    precision: int,
    half: float,
) -> str:
    """Serialize a line structure as a bar drawn across the channel it crosses.

    The bar is centered on the line's midpoint and oriented perpendicular to the
    local flow direction, so a dam/weir reads as a stroke spanning the channel.
    """
    parts = list(_iter_line_parts(geom))
    coords: list[Coord] = []
    for part in parts:
        coords.extend(tuple(c)[:2] for c in part.coords)
    if len(coords) < 2:
        # Degenerate: fall back to a short horizontal bar at the single point.
        cx, cy = coords[0] if coords else (0.0, 0.0)
        x0, y0 = cx - min_x - half, max_y - cy
        x1, y1 = cx - min_x + half, max_y - cy
    else:
        mid = len(coords) // 2
        (ax, ay), (bx, by) = coords[mid - 1], coords[mid]
        # Midpoint of the central segment, in projected space.
        px, py = (ax + bx) / 2.0, (ay + by) / 2.0
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy) or 1.0
        # Perpendicular unit vector, scaled to the bar half-length.
        nx, ny = -dy / length * half, dx / length * half
        # Transform both endpoints into the flipped SVG frame.
        x0, y0 = (px + nx) - min_x, max_y - (py + ny)
        x1, y1 = (px - nx) - min_x, max_y - (py - ny)

    def f(value: float) -> str:
        return format_number(value, precision)

    d = f"M {f(x0)},{f(y0)} L {f(x1)},{f(y1)}"
    return f'      <path id="{element_id}" d="{d}"/>'


def _structure_glyph_element(
    shape: str, element_id: str, cx: float, cy: float, size: float, precision: int
) -> str:
    """Serialize one structure point glyph (square/diamond/triangle/dot)."""
    def f(value: float) -> str:
        return format_number(value, precision)

    if shape == "dot":
        r = format_number(size, _WIDTH_PRECISION)
        return f'      <circle id="{element_id}" cx="{f(cx)}" cy="{f(cy)}" r="{r}"/>'
    if shape == "square":
        pts = [
            (cx - size, cy - size), (cx + size, cy - size),
            (cx + size, cy + size), (cx - size, cy + size),
        ]
    elif shape == "diamond":
        pts = [(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)]
    else:  # triangle
        pts = [(cx, cy - size), (cx + size, cy + size), (cx - size, cy + size)]
    d = f"M {f(pts[0][0])},{f(pts[0][1])} " + " ".join(
        f"L {f(x)},{f(y)}" for x, y in pts[1:]
    ) + " Z"
    return f'      <path id="{element_id}" d="{d}"/>'


def _hydro_structure_group(
    struct_class: str,
    feats: list[tuple],
    style: dict,
    min_x: float,
    max_y: float,
    precision: int,
) -> list[str]:
    """Serialize one ``<g id="hydro_<class>">`` group, dispatching by geometry.

    Each feature is drawn by its geometry kind: points → marker glyph, lines →
    a bar across the channel, polygons → an areal fill/outline path. All three
    kinds may appear under one class (structures span geometry types).
    """
    color = style.get("color", DEFAULT_FALLBACK_COLOR)
    size = float(style.get("size", 1.5))
    fill_mode = style.get("fill", "none")
    glyph = style.get("marker") or HYDRO_STRUCTURE_GLYPHS.get(struct_class, "dot")

    attrs = [f'id="hydro_{struct_class}"', f'data-class="{struct_class}"']
    if glyph == "dot" and fill_mode not in ("solid", "hatch"):
        attrs.append(f'fill="{color}"')
        attrs.append('stroke="none"')
    else:
        sw = format_number(max(size * 0.4, 0.1), _WIDTH_PRECISION)
        attrs.append('fill="none"')
        attrs.append(f'stroke="{color}"')
        attrs.append(f'stroke-width="{sw}"')
    lines = [f"  <g {' '.join(attrs)}>"]

    for feature_id, geom in feats:
        kind = _structure_geometry_kind(geom)
        eid = f"hydro_{struct_class}_{feature_id}"
        if kind == "point":
            cx, cy = _point_xy(geom, min_x, max_y)
            lines.append(
                _structure_glyph_element(glyph, eid, cx, cy, size, precision)
            )
        elif kind == "polygon":
            d = polygon_path_d(geom, min_x, max_y, precision)
            path_attrs = [f'id="{eid}"', f'd="{d}"']
            if fill_mode == "solid":
                op = format_number(float(style.get("opacity", 1.0)), 2)
                path_attrs.append(f'fill="{color}"')
                path_attrs.append(f'fill-opacity="{op}"')
                path_attrs.append('fill-rule="evenodd"')
            else:
                path_attrs.append('fill="none"')
                dash = style.get("dash")
                if dash:
                    path_attrs.append(f'stroke-dasharray="{dash}"')
            lines.append("    <path " + " ".join(path_attrs) + "/>")
        else:  # line → bar across the channel
            lines.append(
                _structure_bar_element(
                    eid, geom, min_x, max_y, precision, _STRUCTURE_BAR_HALF
                )
            )
    lines.append("  </g>")
    return lines


def _hydro_structure_lines(
    items: list[tuple],
    styles: Mapping | None,
    min_x: float,
    max_y: float,
    precision: int,
) -> list[str]:
    """Serialize ``<g id="hydro_structures">`` with one child ``<g>`` per class.

    ``items`` are ``(feature_id, geometry, struct_class)`` tuples carrying already
    projected shapely geometries. Classes are emitted in sorted order and each
    feature is dispatched by geometry kind (point glyph / line bar / areal path)
    so the group is deterministic.
    """
    groups = _group_by_family(items)
    lines = ['  <g id="hydro_structures">']
    for struct_class in sorted(groups):
        style = _merge_style(DEFAULT_HYDRO_STRUCTURE_STYLES, struct_class, styles)
        lines.extend(
            _hydro_structure_group(
                struct_class, groups[struct_class], style, min_x, max_y, precision
            )
        )
    lines.append("  </g>")
    return lines


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


def _glow_filter_lines(radius: float) -> list[str]:
    """SVG ``<filter>`` lines for the Gaussian-blur glow (PRD section 20, Mode B)."""
    std = format_number(radius, _WIDTH_PRECISION)
    return [
        f'    <filter id="{GLOW_FILTER_ID}" x="-20%" y="-20%" width="140%" height="140%">',
        f'      <feGaussianBlur stdDeviation="{std}" result="blur"/>',
        "      <feMerge>",
        '        <feMergeNode in="blur"/>',
        '        <feMergeNode in="SourceGraphic"/>',
        "      </feMerge>",
        "    </filter>",
    ]


def _group_lines(
    group_id: str,
    color: str | None,
    segment_ids: list[int],
    geometries: Mapping[int, Any],
    segment_colors: Mapping[int, str],
    fallback_color: str,
    min_x: float,
    max_y: float,
    precision: int,
    stroke_widths: Mapping[int, float] | None,
    filter_ref: str | None,
) -> list[str]:
    """Serialize a river ``<g>`` layer. ``color=None`` → per-path stroke."""
    attrs = [f'id="{group_id}"']
    if color is not None:
        attrs.append(f'stroke="{color}"')
    if filter_ref is not None:
        attrs.append(f'filter="{filter_ref}"')
    lines = [f"  <g {' '.join(attrs)}>"]
    for sid in segment_ids:
        stroke = None if color is not None else segment_colors.get(sid, fallback_color)
        lines.append(
            _path_element(
                sid, geometries[sid], min_x, max_y, precision, stroke, stroke_widths
            )
        )
    lines.append("  </g>")
    return lines


def _halo_lines(
    group_id: str,
    color: str | None,
    segment_ids: list[int],
    geometries: Mapping[int, Any],
    segment_colors: Mapping[int, str],
    fallback_color: str,
    min_x: float,
    max_y: float,
    precision: int,
    halo_width: str,
) -> list[str]:
    """Serialize a wider, translucent halo ``<g>`` (PRD section 20, Mode A)."""
    opacity = format_number(_HALO_OPACITY, 2)
    attrs = [f'id="{group_id}_glow"']
    if color is not None:
        attrs.append(f'stroke="{color}"')
    attrs.append(f'stroke-width="{halo_width}"')
    attrs.append(f'stroke-opacity="{opacity}"')
    lines = [f"  <g {' '.join(attrs)}>"]
    for sid in segment_ids:
        stroke = None if color is not None else segment_colors.get(sid, fallback_color)
        path_attrs = [f'd="{path_d(geometries[sid], min_x, max_y, precision)}"']
        if stroke is not None:
            path_attrs.append(f'stroke="{stroke}"')
        lines.append("    <path " + " ".join(path_attrs) + "/>")
    lines.append("  </g>")
    return lines


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
    glow: bool = False,
    glow_mode: str = "blur",
    glow_radius: float = 2.0,
    waterbodies: Iterable[tuple] | None = None,
    waterbody_color: str = "#2ec4ff",
    waterbody_stroke_width: float = 0.45,
    waterbody_order: str = "below",
    areal_features: Iterable[tuple] | None = None,
    areal_feature_styles: Mapping[str, Mapping] | None = None,
    point_features: Iterable[tuple] | None = None,
    point_feature_styles: Mapping[str, Mapping] | None = None,
    point_feature_order: str = "above",
    hydro_structures: Iterable[tuple] | None = None,
    hydro_structure_styles: Mapping[str, Mapping] | None = None,
    hydro_structure_order: str = "above",
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
        glow: Whether to add the optional glow effect (PRD section 20).
        glow_mode: ``"blur"`` (Gaussian-blur filter) or ``"vector"`` (halo).
        glow_radius: Glow radius in SVG user units.
        waterbodies: Optional iterable of ``(feature_id, geometry[, wb_class])``
            polygon outlines rendered in a dedicated no-fill layer (Item W3).
            ``None``/empty produces output byte-identical to a river-only render.
        waterbody_color: Stroke color for the waterbody outline layer.
        waterbody_stroke_width: Stroke width for the waterbody outline layer.
        waterbody_order: ``"below"`` places the waterbody layer beneath the
            flowline layers (rivers stay legible); ``"above"`` places it on top.
        areal_features: Optional iterable of ``(feature_id, geometry, family)``
            polygons (wetland/playa/perennial_ice) rendered as per-family
            ``<g id="areal_<family>">`` groups with differentiated fills. Each
            family's ``render_order`` (``"below"`` default / ``"above"``) is read
            from ``areal_feature_styles``. ``None``/empty leaves output unchanged.
        areal_feature_styles: Optional per-family style overrides (color, fill
            mode, opacity, dash, render_order); merged over
            :data:`DEFAULT_AREAL_STYLES`.
        point_features: Optional iterable of ``(feature_id, geometry, family)``
            points (spring/waterfall/rapids) rendered as glyphs under a single
            ``<g id="point_features">`` layer. ``None``/empty leaves output
            unchanged.
        point_feature_styles: Optional per-family style overrides (color, size,
            marker); merged over :data:`DEFAULT_POINT_STYLES`.
        point_feature_order: ``"above"`` (default) draws point glyphs on top of
            everything; ``"below"`` draws them beneath the flowline layers.
        hydro_structures: Optional iterable of ``(feature_id, geometry,
            struct_class)`` engineered structures (dam_weir/gate/gaging_station/
            water_intake_outflow/spillway/lock_chamber/canal_ditch) rendered in a
            dedicated ``<g id="hydro_structures">`` layer, each feature dispatched
            by geometry kind (point glyph / line bar / areal path). ``None``/empty
            leaves output byte-identical to a render with no structures argument.
        hydro_structure_styles: Optional per-class style overrides (color, size,
            fill mode, opacity, dash, marker); merged over
            :data:`DEFAULT_HYDRO_STRUCTURE_STYLES`.
        hydro_structure_order: ``"above"`` (default) draws structures on top of
            the water stack so a dam overlays its channel; ``"below"`` draws them
            beneath the flowline layers.

    Returns:
        The SVG document as a string (trailing newline included). With
        ``glow=False`` the output is identical to the un-glowed render.
    """
    waterbody_items = list(waterbodies) if waterbodies else []
    areal_items = list(areal_features) if areal_features else []
    point_items = list(point_features) if point_features else []
    structure_items = list(hydro_structures) if hydro_structures else []
    min_x, min_y, max_x, max_y = bounds(geometries.values())
    extra_boxes: list[tuple[float, float, float, float]] = []
    if waterbody_items:
        pb = polygon_bounds(item[1] for item in waterbody_items)
        if pb is not None:
            extra_boxes.append(pb)
    if areal_items:
        pb = polygon_bounds(item[1] for item in areal_items)
        if pb is not None:
            extra_boxes.append(pb)
    if point_items:
        pb = _point_bounds(point_items)
        if pb is not None:
            extra_boxes.append(pb)
    if structure_items:
        sb = _structure_bounds(structure_items)
        if sb is not None:
            extra_boxes.append(sb)
    seeded = bool(geometries)
    for pb in extra_boxes:
        if not seeded:
            min_x, min_y, max_x, max_y = pb
            seeded = True
        else:
            min_x, min_y = min(min_x, pb[0]), min(min_y, pb[1])
            max_x, max_y = max(max_x, pb[2]), max(max_y, pb[3])
    width = format_number(max_x - min_x, precision)
    height = format_number(max_y - min_y, precision)
    base_width = format_number(line_width, _WIDTH_PRECISION)

    blur_glow = glow and glow_mode == "blur"
    vector_glow = glow and glow_mode == "vector"
    filter_ref = f"url(#{GLOW_FILTER_ID})" if blur_glow else None
    halo_width = format_number(line_width + 2 * glow_radius, _WIDTH_PRECISION)

    lines: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" width="{width}px" height="{height}px" '
        'fill="none" stroke-linecap="round" stroke-linejoin="round" '
        f'stroke-width="{base_width}">'
    )
    def_body: list[str] = []
    if blur_glow:
        def_body.extend(_glow_filter_lines(glow_radius))
    if areal_items:
        def_body.extend(_areal_pattern_defs(areal_items, areal_feature_styles))
    if def_body:
        lines.append("  <defs>")
        lines.extend(def_body)
        lines.append("  </defs>")
    else:
        lines.append("  <defs/>")
    lines.append('  <g id="background">')
    lines.append(
        f'    <rect x="0" y="0" width="{width}" height="{height}" fill="{background}"/>'
    )
    lines.append("  </g>")

    areal_groups = _group_by_family(areal_items)

    # Areal families default beneath everything (before waterbodies + rivers).
    if areal_items:
        lines.extend(
            _areal_lines_for_order(
                areal_groups, areal_feature_styles, "below", min_x, max_y, precision
            )
        )

    if waterbody_items and waterbody_order == "below":
        lines.extend(
            _waterbody_lines(
                waterbody_items, waterbody_color, waterbody_stroke_width,
                min_x, max_y, precision,
            )
        )

    if point_items and point_feature_order == "below":
        lines.extend(
            _point_features_lines(point_items, point_feature_styles, min_x, max_y, precision)
        )

    if structure_items and hydro_structure_order == "below":
        lines.extend(
            _hydro_structure_lines(
                structure_items, hydro_structure_styles, min_x, max_y, precision
            )
        )

    grouped: set[int] = set().union(*watersheds.values()) if watersheds else set()

    # Ordered river layers: watershed groups (sorted) then any unassigned.
    river_groups: list[tuple[str, str | None, list[int]]] = []
    for code in sorted(watersheds):
        segment_ids = sorted(sid for sid in watersheds[code] if sid in geometries)
        if not segment_ids:
            continue
        color = segment_colors.get(segment_ids[0], fallback_color)
        river_groups.append((f"watershed_{code}", color, segment_ids))
    unassigned = sorted(sid for sid in geometries if sid not in grouped)
    if unassigned:
        river_groups.append(("rivers_unassigned", None, unassigned))

    for group_id, color, segment_ids in river_groups:
        if vector_glow:
            lines.extend(
                _halo_lines(
                    group_id, color, segment_ids, geometries, segment_colors,
                    fallback_color, min_x, max_y, precision, halo_width,
                )
            )
        lines.extend(
            _group_lines(
                group_id, color, segment_ids, geometries, segment_colors,
                fallback_color, min_x, max_y, precision, stroke_widths, filter_ref,
            )
        )

    if waterbody_items and waterbody_order == "above":
        lines.extend(
            _waterbody_lines(
                waterbody_items, waterbody_color, waterbody_stroke_width,
                min_x, max_y, precision,
            )
        )

    if areal_items:
        lines.extend(
            _areal_lines_for_order(
                areal_groups, areal_feature_styles, "above", min_x, max_y, precision
            )
        )

    if point_items and point_feature_order == "above":
        lines.extend(
            _point_features_lines(point_items, point_feature_styles, min_x, max_y, precision)
        )

    if structure_items and hydro_structure_order == "above":
        lines.extend(
            _hydro_structure_lines(
                structure_items, hydro_structure_styles, min_x, max_y, precision
            )
        )

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


def flow_widths(
    flows: Mapping[int, float],
    base_width: float,
    max_scale: float = 6.0,
    floor: float = 1e-2,
) -> dict[int, float]:
    """Scale stroke width by discharge, so each channel widens with its flow.

    Unlike :func:`stream_order_widths` (which steps up only at Strahler-order
    confluences), this uses the NHDPlus EROM mean-annual discharge (``QAMA``,
    cfs) so a channel visibly widens at *every* tributary junction — width tracks
    flow "at that point." Discharge spans ~5 orders of magnitude (a headwater
    trickle to the Columbia), so the mapping is logarithmic: the network's
    smallest flow maps to ``base_width`` and its largest to
    ``base_width * max_scale``, interpolating on ``log(flow)``. Deterministic; a
    degenerate (single-value) network yields a uniform ``base_width``.

    Args:
        flows: Mapping of ``segment_id`` -> discharge (any positive flow metric).
        base_width: Stroke width at the smallest flow.
        max_scale: Multiplier applied at the largest flow.
        floor: Minimum flow substituted for non-positive values before the log
            (keeps zero/So headwaters finite and at ``base_width``).

    Returns:
        Mapping of ``segment_id`` -> stroke width.
    """
    top = base_width * max_scale
    logs = {sid: math.log(max(q, floor)) for sid, q in flows.items()}
    if not logs:
        return {}
    lo, hi = min(logs.values()), max(logs.values())
    if hi - lo < 1e-9:
        return {sid: base_width for sid in flows}
    span = hi - lo
    return {
        sid: base_width + (top - base_width) * ((v - lo) / span)
        for sid, v in logs.items()
    }


#: Elevation ramp anchors for :func:`hypsometric_colors`: deep blue (sea level)
#: → white (summit). The low anchor stays visibly saturated (not near-black) so
#: tidewater reaches read as blue against a dark background. Mirrors
#: ``tools/render_state_mono.py`` so the tool and pipeline share one ramp.
_HYPSO_LOW = (26, 72, 156)
_HYPSO_HIGH = (255, 255, 255)


def scaled_widths(
    metric: Mapping[int, float],
    *,
    width_min: float,
    width_max: float,
    gamma: float = 1.0,
    log: bool = False,
) -> dict[int, float]:
    """Map a per-segment metric onto ``[width_min, width_max]`` via a shaped ramp.

    Normalizes ``metric`` to ``[0, 1]`` across the network (on ``log(metric)``
    when ``log`` is set — appropriate for discharge, which spans orders of
    magnitude), applies ``t ** gamma`` shaping, then maps to the width band. This
    is the general width resolver behind the ``width_by=flow`` art-direction
    option: the pipeline feeds it stream orders (``log=False``); the tools feed
    it discharge (``log=True``). Deterministic; a degenerate (empty or
    single-value) network yields a uniform ``width_min``.

    Args:
        metric: Mapping of ``segment_id`` -> a non-negative flow/order metric.
        width_min: Stroke width at the smallest metric value.
        width_max: Stroke width at the largest metric value.
        gamma: Shaping exponent (``> 0``); ``> 1`` keeps more channels thin,
            ``< 1`` widens mid-range channels.
        log: Normalize on ``log(max(metric, 1e-2))`` instead of the raw value.

    Returns:
        Mapping of ``segment_id`` -> stroke width.
    """
    if not metric:
        return {}
    if log:
        vals = {sid: math.log(max(v, 1e-2)) for sid, v in metric.items()}
    else:
        vals = {sid: float(v) for sid, v in metric.items()}
    lo, hi = min(vals.values()), max(vals.values())
    span = hi - lo
    if span < 1e-9:
        return {sid: width_min for sid in metric}
    return {
        sid: width_min + (width_max - width_min) * ((v - lo) / span) ** gamma
        for sid, v in vals.items()
    }


def fixed_flow_span(
    values: Iterable[float], *, floor: float = 1e-2
) -> tuple[float, float]:
    """Return the fixed ``(lo, hi)`` log-span over *all* ``values``.

    This is the "compute once, hold fixed" trick behind month-by-month flow
    rendering: one log-span computed across every month's flows so that a single
    flow always maps to the same width and seasonal swell/retreat is visible
    (per-frame renormalization would hide it). ``lo``/``hi`` are the logs of the
    smallest/largest positive value (floored at ``floor``). Empty or all
    non-positive input is degenerate and yields ``(log(floor), log(floor))``.

    Args:
        values: Any iterable of flows (across all frames).
        floor: Minimum flow substituted before the log.

    Returns:
        ``(lo, hi)`` log-span endpoints.
    """
    positive = [v for v in values if v > 0.0]
    if not positive:
        l = math.log(floor)
        return (l, l)
    lo = math.log(max(min(positive), floor))
    hi = math.log(max(max(positive), floor))
    return (lo, hi)


def widths_on_span(
    flows: Mapping[int, float],
    lo: float,
    hi: float,
    *,
    width_min: float,
    width_max: float,
    floor: float = 1e-2,
) -> dict[int, float]:
    """Map one frame's ``flows`` onto ``[width_min, width_max]`` on a fixed span.

    Each flow is placed on the *fixed* ``(lo, hi)`` log-span from
    :func:`fixed_flow_span` via ``t = clip((log(max(q, floor)) - lo) /
    max(hi - lo, 1e-9), 0, 1)`` and linearly interpolated to the width band. The
    span is held fixed (clamped, not renormalized) so the same flow always yields
    the same width across frames.

    Args:
        flows: Mapping of ``segment_id`` -> flow for this frame.
        lo: Low endpoint of the fixed log-span.
        hi: High endpoint of the fixed log-span.
        width_min: Stroke width at ``lo``.
        width_max: Stroke width at ``hi``.
        floor: Minimum flow substituted before the log.

    Returns:
        Mapping of ``segment_id`` -> stroke width.
    """
    span = max(hi - lo, 1e-9)
    return {
        sid: width_min
        + (width_max - width_min)
        * min(max((math.log(max(q, floor)) - lo) / span, 0.0), 1.0)
        for sid, q in flows.items()
    }


def monthly_width_frames(
    monthly: Mapping[int, list[float]],
    *,
    width_min: float,
    width_max: float,
    floor: float = 1e-2,
) -> list[dict[int, float]]:
    """Return 12 per-month width dicts on one shared fixed span.

    ``monthly`` maps ``segment_id`` -> a length-12 flow series. A single
    :func:`fixed_flow_span` is computed across *all* months' flows, then each
    month is mapped onto it with :func:`widths_on_span`, so seasonal swell and
    retreat is visible frame to frame.

    Args:
        monthly: Mapping of ``segment_id`` -> length-12 flow series.
        width_min: Stroke width at the span's low endpoint.
        width_max: Stroke width at the span's high endpoint.
        floor: Minimum flow substituted before the log.

    Returns:
        A list of 12 ``{segment_id: width}`` dicts.
    """
    lo, hi = fixed_flow_span(
        (q for series in monthly.values() for q in series), floor=floor
    )
    return [
        widths_on_span(
            {sid: series[m] for sid, series in monthly.items()},
            lo,
            hi,
            width_min=width_min,
            width_max=width_max,
            floor=floor,
        )
        for m in range(12)
    ]


def hypsometric_colors(
    elevations: Mapping[int, float],
    *,
    gamma: float = 0.75,
    anchor: float | None = None,
    low: tuple[int, int, int] = _HYPSO_LOW,
    high: tuple[int, int, int] = _HYPSO_HIGH,
) -> dict[int, str]:
    """Map per-segment elevation (m) onto a deep-blue → white hypsometric tint.

    ``t = clip(elev / anchor, 0, 1) ** gamma``; sea level (``t=0``) is ``low``
    and the anchor elevation (``t=1``) is ``high``. ``anchor`` defaults to the
    maximum elevation in ``elevations``; a percentile can be passed to pull more
    of the high country toward white. ``gamma < 1`` brightens mid-slopes. This is
    the ``color_by=elevation`` primitive, promoted from
    ``tools/render_state_mono.py`` so both share one tested ramp. Deterministic;
    a degenerate (all sea-level / non-positive anchor) input yields all ``low``.

    Args:
        elevations: Mapping of ``segment_id`` -> elevation in metres.
        gamma: Ramp-shaping exponent (``> 0``).
        anchor: Elevation mapped to ``high`` (defaults to the max elevation).
        low: RGB triple for sea level.
        high: RGB triple for the anchor (summit).

    Returns:
        Mapping of ``segment_id`` -> hex color string.
    """
    if not elevations:
        return {}
    emax = anchor if anchor is not None else max(elevations.values())
    lr, lg, lb = low
    hr, hg, hb = high
    colors: dict[int, str] = {}
    for sid, elev in elevations.items():
        if emax <= 0:
            t = 0.0
        else:
            t = min(max(elev / emax, 0.0), 1.0) ** gamma
        r = round(lr + (hr - lr) * t)
        g = round(lg + (hg - lg) * t)
        b = round(lb + (hb - lb) * t)
        colors[sid] = f"#{r:02x}{g:02x}{b:02x}"
    return colors
