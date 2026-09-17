# Implementation Report: Streaming SVG writer (Item #108)

## Summary

Added `render_svg_stream(f, ...)` alongside `render_svg() -> str` in
`src/rendering.py`. The streaming path writes SVG lines directly to a file
object, eliminating the need to hold the entire document in memory at once —
critical for continent-scale renders with ~5M `<path>` elements (~400 MB).

## Changes

| File | Change |
|------|--------|
| `src/rendering.py` | Extracted rendering body into `_render_lines(...)` generator; `render_svg` collects and joins (same behavior); new `render_svg_stream(f, ...)` writes line-by-line; added to `__all__` |
| `src/pipeline.py` | `_generate_svg_stage` uses `render_svg_stream` with `io.StringIO` instead of `render_svg`; same string artifact, exercises the streaming code path |
| `tests/test_rendering.py` | 3 new tests: byte-identical (plain + glow), valid SVG structure |

## Design decisions

- **Generator extraction (`_render_lines`):** avoids duplicating the entire
  rendering body. Both `render_svg` and `render_svg_stream` delegate to it.
  All existing helpers (`_group_lines`, `_waterbody_lines`, etc.) continue to
  return `list[str]`; the generator `yield from`s them.
- **Pipeline uses StringIO:** the pipeline writes through the streaming path
  (proving it works in production) but captures the result in a `StringIO` for
  the optimizer and sha256 stages. A future CONUS optimization can write directly
  to a file and compute sha256 incrementally.
- **Byte-identical:** the tests assert `render_svg(...) == render_svg_stream(StringIO, ...)`.
  The separator logic is `"\n"` per line + trailing newline, matching `"\n".join(lines) + "\n"`.

## Test results

- `tests/test_rendering.py`: **13/13 passed** (10 existing + 3 new streaming)
- Full suite: **1094 passed**, 0 failures
- Recipe roundtrip: 11 passed
