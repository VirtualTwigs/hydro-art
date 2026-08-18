# Spec — Hillshade print compositing (roadmap #30)

## Overview

Add `src/compositing.py` — a pure, offline, numpy-only module that converts a
hillshade `RasterGrid` into a tinted RGBA relief background and alpha-composites
the rasterized river-art layers over it. Add `tools/render_terrain_print.py` — a
thin, non-offline executor that wires a region's real DEM through the seam into
the shared render recipe.

## `src/compositing.py` API

```python
class CompositingError(Exception): ...

def shade_to_background(
    grid: RasterGrid,
    *,
    tint: tuple[int, int, int] | None = None,
    opacity: float = 1.0,
) -> np.ndarray:
    """Hillshade RasterGrid (0-255, nodata sentinel) -> HxWx4 uint8 RGBA.

    Grayscale (r=g=b=shade) unless ``tint`` (an RGB colour) is given, in which
    case rgb = round(shade/255 * tint). Valid cells get alpha round(255*opacity);
    nodata cells get alpha 0 (transparent). Raises CompositingError for opacity
    outside [0,1] or a malformed tint.
    """

def solid_canvas(
    height: int, width: int, color: tuple[int, int, int] = (0, 0, 0)
) -> np.ndarray:
    """Opaque HxWx4 uint8 RGBA canvas of a single colour (alpha 255)."""

def alpha_over(base: np.ndarray, over: np.ndarray) -> np.ndarray:
    """Porter-Duff 'over' of two equal-shape HxWx4 uint8 RGBA arrays -> HxWx4
    uint8 (straight/unpremultiplied alpha; out_a==0 -> rgb 0). Raises
    CompositingError on shape/dtype/channel mismatch."""

def composite_over_background(
    background: np.ndarray, layers: Sequence[np.ndarray]
) -> np.ndarray:
    """Fold ``layers`` (each HxWx4 uint8) over ``background`` in order via
    ``alpha_over`` -> HxWx4 uint8. Empty ``layers`` returns a copy of the
    background."""
```

### Compositing math (`alpha_over`)

Straight-alpha "over", computed in float64 then rounded to uint8:

```
ab = base_a/255 ; ao = over_a/255
oa = ao + ab*(1-ao)
orgb = where(oa>0, (over_rgb*ao + base_rgb*ab*(1-ao)) / oa, 0)
out = round(clip([orgb, oa*255], 0, 255)).astype(uint8)
```

### Print composite chain (how the tool uses the seam)

```
base   = solid_canvas(h, w, base_color)         # opaque backdrop
relief = shade_to_background(hillshade(dem), tint=..., opacity=...)  # resized to (h,w) by the tool
result = composite_over_background(base, [relief, *river_layers])
```

Because the relief is "just another RGBA layer" over the solid base, no
relief-specific compositing branch is needed.

## `tools/render_terrain_print.py` (non-offline)

Thin CLI: `--region` (+ `--cache-dir`), output PNG, `--width`, sun params
(`--azimuth`/`--altitude`/`--z-factor`), relief `--tint`/`--relief-opacity`,
`--min-order`. Flow: `region_bounds` → `acquire_dem_for_settings` →
`normalize_dem` (EPSG:5070, region extent) → `hillshade` → `shade_to_background`;
build the river art via `render_common` (clip flowlines, build inputs, render art
SVG), split+rasterize the river layers to RGBA (as `rasterize_layered` does),
resize the relief to the canvas, and `composite_over_background`. The DEM relief
and flowlines share the EPSG:5070 frame/extent so they register. Reads a real
(possibly NAS) cache + resvg → outside the offline suite.

## Testing

- `tests/test_compositing.py` (TG1+TG2, offline, numpy hand-built inputs).
- Smoke (TG3): a synthetic DEM grid through hillshade → seam → PNG on disk.

## Determinism & safety

Pure functions, explicit float→uint8 rounding, boundary validation raising
`CompositingError`. No global state; no `Settings`/`PIPELINE_STAGES` changes;
default `tools/rasterize_layered.py` behaviour untouched (the flat-black path
still exists — the new tool is a separate entry point).
