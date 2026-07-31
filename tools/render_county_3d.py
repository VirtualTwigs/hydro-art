"""Render the Clark County river network as a tilted, glowing 3D art image.

Unlike a DEM-draped terrain, elevation here is *derived from the hydrography
itself*: each flowline's USGS Strahler ``StreamOrde`` sets its height, so
headwater tributaries (order 1) ride high and high-order mainstems sink into the
valley floors. The network therefore cascades into its own trunks without any
external elevation data. The lifted 3D field is then rotated (yaw) and tilted
to a low camera elevation and orthographically projected, painter-sorted
back-to-front, and drawn with a neon glow — colored by HUC sub-watershed, with
per-stream width scaled by flow (order), matching the 2-D render.

    python tools/render_county_3d.py --elev 24 --yaw 22 --amp 0.5

This reuses the deterministic clip + sub-watershed join from
``render_county_clip.py``; terrain is a stylized hydrology-derived field, not
surveyed elevation.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from tools.render_county_clip import (
    CLARK_BBOX_4326,
    _hex_rgb,
    assign_subwatersheds,
    bbox_boundary,
    build_inputs,
    clip_flowlines,
)


def _parts(geom):
    """Yield each part of a (Multi)LineString as a list of (x, y) (drops any Z)."""
    if geom.geom_type == "MultiLineString":
        for p in geom.geoms:
            yield [(c[0], c[1]) for c in p.coords]
    elif geom.geom_type == "LineString":
        yield [(c[0], c[1]) for c in geom.coords]


def build_segments(geoms, orders, flows, colors, max_order, amp):
    """Return segments ``(verts[(X,Y,Z)], rgb, wt)`` in normalized space.

    Elevation ``Z`` is derived from Strahler ``order`` (headwaters high, mainstem
    at 0). ``wt`` in [0, 1] is a log-scaled flow factor from NHDPlus EROM
    mean-annual discharge (``QAMA``); the renderer maps it to stroke width, so a
    channel widens with actual flow at that point, not just at order jumps.
    """
    xs, ys = [], []
    for g in geoms:
        for part in _parts(g):
            for x, y in part:
                xs.append(x); ys.append(y)
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    s = 2.0 / max(maxx - minx, maxy - miny)  # fit into ~[-1, 1], aspect-true

    span = max(1, max_order - 1)
    logs = [math.log(max(f, 1e-2)) for f in flows]
    lo, hi = min(logs), max(logs)
    fspan = (hi - lo) or 1.0
    segs = []
    for i, g in enumerate(geoms):
        rgb = _hex_rgb(colors[i])
        # Headwaters (order 1) high, mainstem (max order) at 0.
        z = amp * ((max_order - orders[i]) / span)
        wt = (logs[i] - lo) / fspan
        for part in _parts(g):
            verts = [((x - cx) * s, (y - cy) * s, z) for x, y in part]
            if len(verts) > 1:
                segs.append((verts, rgb, wt))
    return segs


def project(segs, yaw_deg, elev_deg):
    """Rotate (yaw about vertical, tilt to camera elevation) + orthographic project.

    Camera elevation ``el`` measures the angle above the horizon: 90 = top-down
    (flat), small = low raking angle where the stream-order relief reads most.
    Returns per-segment (screen_xy list, rgb, order, mean_depth), plus screen bounds.
    """
    a = math.radians(yaw_deg)
    el = math.radians(elev_deg)
    ca, sa, ce, se = math.cos(a), math.sin(a), math.cos(el), math.sin(el)
    out = []
    minsx = minsy = math.inf
    maxsx = maxsy = -math.inf
    for verts, rgb, wt in segs:
        pts = []
        depth = 0.0
        for X, Y, Z in verts:
            x1 = X * ca - Y * sa
            y1 = X * sa + Y * ca
            sx = x1
            sy = y1 * se + Z * ce            # elevation lifts point up-screen
            depth += y1 * ce - Z * se        # larger = farther from camera
            pts.append((sx, sy))
            minsx, maxsx = min(minsx, sx), max(maxsx, sx)
            minsy, maxsy = min(minsy, sy), max(maxsy, sy)
        out.append((pts, rgb, wt, depth / len(verts)))
    return out, (minsx, minsy, maxsx, maxsy)


def render(projected, sbounds, width, ss, min_px, max_px, glow):
    minsx, minsy, maxsx, maxsy = sbounds
    margin = int(width * 0.06) * ss
    draw_w = width * ss
    scale = (draw_w - 2 * margin) / (maxsx - minsx)
    draw_h = int((maxsy - minsy) * scale + 2 * margin)

    def to_px(pts):
        return [
            (margin + (sx - minsx) * scale,
             margin + (maxsy - sy) * scale)   # flip: elevation up
            for sx, sy in pts
        ]

    # Painter's order: far (large depth) first, near last.
    projected = sorted(projected, key=lambda t: t[3], reverse=True)

    base = (min_px * ss)
    core = Image.new("RGB", (draw_w, draw_h), (0, 0, 0))
    cd = ImageDraw.Draw(core)
    halo = Image.new("RGB", (draw_w, draw_h), (0, 0, 0)) if glow else None
    hd = ImageDraw.Draw(halo) if glow else None

    for pts, rgb, wt, _ in projected:
        px = to_px(pts)
        w = base + (max_px * ss - base) * wt
        if glow:
            hd.line(px, fill=rgb, width=int(w * 3) + ss, joint="curve")
        cd.line(px, fill=rgb, width=max(ss, int(w)), joint="curve")

    if glow:
        halo = halo.filter(ImageFilter.GaussianBlur(radius=3 * ss))
        # Screen-blend the blurred halo under the crisp cores.
        core = Image.blend(core, _screen(core, halo), 0.85)
    img = core.resize((width, draw_h // ss), Image.LANCZOS)
    return img


def _screen(a, b):
    """Screen blend two RGB images (additive-ish glow)."""
    an = np.asarray(a, dtype=np.float32) / 255
    bn = np.asarray(b, dtype=np.float32) / 255
    out = (1 - (1 - an) * (1 - bn)) * 255
    return Image.fromarray(out.astype(np.uint8), "RGB")


def draw_caption(img, text):
    d = ImageDraw.Draw(img)
    W = img.size[0]
    fs = max(22, W // 90)
    for p in ("/System/Library/Fonts/SFNSMono.ttf",
              "/System/Library/Fonts/Menlo.ttc", "/Library/Fonts/Arial.ttf"):
        try:
            font = ImageFont.truetype(p, size=fs); break
        except Exception:  # noqa: BLE001
            font = ImageFont.load_default()
    d.text((fs, fs), text, fill=(150, 160, 180), font=font)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--huc-level", default="HUC10", choices=["HUC8", "HUC10", "HUC12"])
    ap.add_argument("--yaw", type=float, default=22.0)
    ap.add_argument("--elev", type=float, default=24.0,
                    help="Camera elevation above horizon (deg); 90=top-down.")
    ap.add_argument("--amp", type=float, default=0.5,
                    help="Stream-order relief amplitude (normalized units).")
    ap.add_argument("--width", type=int, default=3000)
    ap.add_argument("--ss", type=int, default=2, help="Supersample factor (AA).")
    ap.add_argument("--min-px", type=float, default=0.5)
    ap.add_argument("--max-px", type=float, default=5.0)
    ap.add_argument("--no-glow", action="store_true")
    args = ap.parse_args()

    print("clipping Clark County flowlines ...")
    boundary = bbox_boundary(CLARK_BBOX_4326)
    geoms, orders, flows, _basins = clip_flowlines(boundary, "1708", 1)
    print(f"total kept: {len(geoms)}")

    digits = int(args.huc_level[3:])
    codes, _names = assign_subwatersheds(geoms, digits)
    _, segment_colors, _watersheds, _cc = build_inputs(geoms, codes)
    colors = [segment_colors[i] for i in range(len(geoms))]
    max_order = max(orders)
    print(f"stream orders 1..{max_order}; flow 0..{max(flows):.0f} cfs; "
          f"relief amp={args.amp}")

    segs = build_segments(geoms, orders, flows, colors, max_order, args.amp)
    projected, sbounds = project(segs, args.yaw, args.elev)
    img = render(projected, sbounds, args.width, args.ss,
                 args.min_px, args.max_px, not args.no_glow)
    draw_caption(
        img,
        f"Clark County, WA — 3D hydrography (yaw {args.yaw:.0f} / elev "
        f"{args.elev:.0f}) · height = stream order · width = flow",
    )
    out = "output/clark_county_3d.png"
    img.save(out)
    print(f"wrote {out} ({img.size[0]}x{img.size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
