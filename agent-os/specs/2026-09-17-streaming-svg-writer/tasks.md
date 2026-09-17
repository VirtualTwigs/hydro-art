# Tasks: Streaming SVG writer (Item #108)

## Task Group 1: Streaming renderer + pipeline integration

- [x] 1.1 Extract the body of `render_svg` into `_render_lines(...)` generator that yields each SVG line
- [x] 1.2 Rewrite `render_svg` to collect from `_render_lines` and join (same behavior, byte-identical)
- [x] 1.3 Add `render_svg_stream(f: IO, ...)` that writes each line to `f` with newlines
- [x] 1.4 Export `render_svg_stream` in `__all__`
- [x] 1.5 Wire `_generate_svg_stage` in `src/pipeline.py` to use `render_svg_stream` (write to StringIO, extract string)
- [x] 1.6 Write tests: 3 streaming tests (byte-identical plain, byte-identical with glow, valid SVG structure)
- [x] 1.7 Run `tests/test_rendering.py` — all 13 pass
- [x] 1.8 Run full suite — 1094 passed, no regressions
