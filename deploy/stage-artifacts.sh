#!/usr/bin/env bash
# Stage the demo's runtime assets into deploy/output/, a real local dir the
# Docker VM can bind-mount. The repo's own output/ is a symlink to the NAS,
# which Docker Desktop's file sharing can't traverse — hence this stage.
#
# Two groups:
#   1. The display SVGs the viewer pages (3d.html, etc.) fetch, copied as-is.
#   2. Web-optimized landing assets under deploy/output/landing/ that the
#      customer landing (web/start.html) shows — real Clark County / Washington
#      renders down-scaled to WebP (static + animated) so the page stays light.
#
# Re-run after re-rendering any source (tools/render_state_svg.py,
# tools/render_county_clip.py, tools/render_monthly.py, tools/render_infographic*,
# tools/build_report_card.py — the report card is composed from notebooks/figures/).
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src_root="$repo_root/output"
dest="$repo_root/deploy/output"
mkdir -p "$dest"

require_src() {
  # require_src <path>  → echo the path, or fail with a hint.
  if [[ ! -f "$1" ]]; then
    echo "missing: $1 (is the NAS mounted? render it — see tools/)" >&2
    exit 1
  fi
  printf '%s' "$1"
}

# --- 1. Display SVGs (copied verbatim) -------------------------------------
for name in oregon_display.svg washington_display.svg; do
  cp -f "$(require_src "$src_root/$name")" "$dest/$name"
  echo "staged $name ($(du -h "$dest/$name" | cut -f1))"
done

# --- 2. Landing assets (down-scaled WebP) ----------------------------------
# Needs sips (macOS), cwebp, and gif2webp on PATH. If any is absent we skip the
# landing set with a warning — the display SVGs above are enough for the other
# viewer pages; only web/start.html degrades (broken <img>s) until you re-run
# this on a machine that has the WebP tools.
landing="$dest/landing"
if command -v cwebp >/dev/null 2>&1 && command -v gif2webp >/dev/null 2>&1 && command -v sips >/dev/null 2>&1; then
  mkdir -p "$landing"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT

  # static PNG → resize longest side → WebP
  stage_png() { # <src.png> <out.webp> <max_px> <quality>
    local s; s="$(require_src "$1")"
    sips -Z "$3" "$s" --out "$tmp/_s.png" >/dev/null 2>&1
    cwebp -quiet -q "$4" "$tmp/_s.png" -o "$landing/$2"
    echo "staged landing/$2 ($(du -h "$landing/$2" | cut -f1))"
  }
  # animated GIF → lossy animated WebP
  stage_gif() { # <src.gif> <out.webp> <quality>
    local s; s="$(require_src "$1")"
    gif2webp -quiet -lossy -q "$3" -m 6 -min_size "$s" -o "$landing/$2"
    echo "staged landing/$2 ($(du -h "$landing/$2" | cut -f1))"
  }

  stage_png "$src_root/clark_county.png"            clark-poster.webp 1500 82
  stage_png "$src_root/watershed_report_card.png"   clark-report.webp 1400 86
  stage_png "$src_root/washington_elevation_peak.png" wa-elevation.webp 1600 82
  stage_gif "$src_root/monthly_flow_clark_county_24f.gif" clark-flow.webp 50
else
  echo "WARN: cwebp/gif2webp/sips not all present — skipping landing/ assets." >&2
  echo "      web/start.html images will 404 until you re-run this with the WebP tools installed." >&2
fi
