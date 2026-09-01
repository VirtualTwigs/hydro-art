# Pre-analysis watch-list — Golden-output fixtures (#40)

_Written before implementation (Epoch 8/9/12 practice): the highest-risk items to
grade the retrospective against, fixed up front so findings can't be quietly reframed._

1. **DEM checksum stability.** The array→sha must be canonical: same grid → same hash
   across runs/platforms (little-endian float64, explicit dtype cast, NaN normalized).
   Risk: hashing `ndarray.tobytes()` on a non-contiguous or native-endian array yields a
   host-dependent digest that flags false drift. *Grade: is the hash byte-layout-pinned
   and NaN-safe, proven by an offline test that mutates each field?*

2. **Same-host vs cross-host honesty.** A DEM mosaic golden is only a same-host regression
   (GDAL/PROJ version-sensitive), unlike the pure-Python SVG sha. Risk: overselling it as a
   portable invariant. *Grade: is the caveat recorded in the spec, the module docstring, and
   the fixture, and is the SVG sha still the primary cross-host invariant?*

3. **#39 regression.** Evolving the registry schema must not break the shipped SVG
   determinism behavior or its tests. Risk: schema churn silently changes run-to-run/golden
   semantics. *Grade: do the #39 semantics survive (run-to-run, soft-record-me, mismatch),
   with SVG-only still expressible, and does the full offline suite stay green?*

4. **Offline-suite discipline.** No GDAL/network in `src/`+`tests/`; DEM acquisition stays in
   `tools/`; `determinism.py` stays stdlib-only. Risk: pulling `normalize_dem`/rasterio into
   the pure core to compute the checksum. *Grade: does `determinism.py` stay stdlib-only, and
   does `grid_checksum` live in the already-numpy `raster.py` with an offline test?*

5. **Byte-identical 2D output.** Nothing enters `PIPELINE_STAGES`; no rendered bytes change.
   *Grade: structurally held (no pipeline stage touched, DEM subsystem still parallel)?*

6. **Actually commit a fixture (don't just build the mechanism).** #39 already built the
   mechanism; #40's deliverable is a *committed* golden for a real tiny county. Risk: shipping
   more plumbing and no fixture. *Grade: is `tests/fixtures/golden/registry.json` committed
   with a real county's SVG sha (+ DEM sha if the host allowed), or is the DEM half honestly
   deferred to the GDAL/NAS host like #42?*
