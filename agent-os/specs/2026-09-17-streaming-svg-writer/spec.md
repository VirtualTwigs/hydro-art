# Spec: Streaming SVG writer (Item #108)

## Overview

Add `render_svg_stream(f: IO, ...)` alongside the existing `render_svg() -> str`
in `src/rendering.py`. The streaming path writes SVG lines directly to a file
object, eliminating the ~400 MB in-memory string that `render_svg` builds for
continent-scale renders (~5M `<path>` elements).

## Approach

Refactor the rendering body into an internal generator `_render_lines(...)` that
yields each SVG line. Both public functions delegate to it:

- `render_svg(...)` — collects all lines into `"\n".join(lines) + "\n"` (existing
  behavior, byte-identical)
- `render_svg_stream(f, ...)` — writes each line followed by `"\n"` to `f`

This avoids duplicating the rendering logic. All existing helper functions
(`_group_lines`, `_waterbody_lines`, etc.) continue to return `list[str]`; the
generator yields from them.

## Pipeline integration

`_generate_svg_stage` in `src/pipeline.py` gains a streaming code path:

- Writes SVG directly to a temp file via `render_svg_stream`
- Reads the file back into `ctx.artifacts["svg"]` (still needed by
  `_optimize_svg_stage` and sha256)
- For small regions this adds a disk round-trip but is functionally identical
- For CONUS, a future optimization can skip the read-back and compute sha256
  incrementally

## Byte-identical constraint

`render_svg_stream(f)` must produce the exact same bytes as `render_svg()` for
identical inputs. The test suite asserts this directly.

## Non-goals

- Incremental sha256 during streaming (future CONUS optimization)
- Streaming SVG optimizer (svgo already reads files)
- Changes to the export stage
