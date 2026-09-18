#!/usr/bin/env python3
"""Real-data smoke harness (roadmap #41 + #42 real-tile half, non-offline).

Fires exactly the branches that injected fakes skip in the offline suite:
the real rasterio warp, multi-tile mosaic alignment, and cross-device SMB
mover. Each subcheck is independently runnable and reports pass/fail;
``--all`` is the epoch-gate roll-up.

Gated: only runs when ``HYDRO_ART_REAL_DATA=1`` is set AND the cache dir
exists. The offline suite is never affected.

    HYDRO_ART_REAL_DATA=1 python tools/smoke_real_paths.py --all
    HYDRO_ART_REAL_DATA=1 python tools/smoke_real_paths.py --warp
    HYDRO_ART_REAL_DATA=1 python tools/smoke_real_paths.py --mosaic
    HYDRO_ART_REAL_DATA=1 python tools/smoke_real_paths.py --mover
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.crs import INTERNAL_CRS  # noqa: E402

DEM_CACHE = Path("cache/dem/1")
NAS_MOUNT = Path("/Volumes/home/data/hydro-art")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _find_tiles() -> list[Path]:
    """Find cached 3DEP COG tiles."""
    if not DEM_CACHE.exists():
        return []
    return sorted(DEM_CACHE.glob("USGS_*.tif"))


def _tile_lat(path: Path) -> int | None:
    """Extract latitude from a tile name like USGS_1_n47w122.tif."""
    name = path.stem  # USGS_1_n47w122
    for part in name.split("_"):
        if part.startswith("n") and len(part) >= 3:
            try:
                return int(part[1:3])
            except ValueError:
                continue
    return None


# -- (a) Non-identity warp ---------------------------------------------------


def check_warp() -> bool:
    """Warp a real 3DEP tile from EPSG:4269 to INTERNAL_CRS (EPSG:5070).

    Asserts: output CRS is EPSG:5070, transform is north-up, nodata preserved,
    extent is sane (non-empty array).
    """
    tiles = _find_tiles()
    if not tiles:
        print("  SKIP: no cached 3DEP tiles found in", DEM_CACHE)
        return True  # skip, not fail

    tile = tiles[0]
    print(f"  tile: {tile.name}")

    from src.raster_io import RasterioRasterReader, RasterioReprojector

    reader = RasterioRasterReader()
    grid = reader.read(str(tile))
    print(f"  source CRS: {grid.crs}, shape: {grid.values.shape}")

    if grid.crs == INTERNAL_CRS:
        print("  SKIP: tile already in INTERNAL_CRS (identity path, no warp)")
        return True

    reprojector = RasterioReprojector()
    warped = reprojector.reproject(grid, INTERNAL_CRS)

    # Assertions
    ok = True
    if warped.crs != INTERNAL_CRS:
        print(f"  FAIL: output CRS is {warped.crs!r}, expected {INTERNAL_CRS}")
        ok = False
    else:
        print(f"  output CRS: {warped.crs}")

    # North-up: pixel_height > 0 (our convention stores it positive, origin_y is top)
    if warped.transform.pixel_height <= 0:
        print(f"  FAIL: pixel_height {warped.transform.pixel_height} is not positive (not north-up)")
        ok = False
    else:
        print(f"  north-up: pixel_height={warped.transform.pixel_height:.6f}")

    if warped.values.size == 0:
        print("  FAIL: warped array is empty")
        ok = False
    else:
        print(f"  warped shape: {warped.values.shape}")

    # Nodata preserved (not invented)
    if grid.nodata is not None and warped.nodata is None:
        print("  FAIL: source had nodata but warped lost it")
        ok = False
    else:
        print(f"  nodata: {warped.nodata}")

    print(f"  {'PASS' if ok else 'FAIL'}: non-identity warp")
    return ok


# -- (b) Multi-tile mosaic alignment -----------------------------------------


def check_mosaic() -> bool:
    """Mosaic >=2 real tiles at different latitudes, assert uniform pixel size.

    This is the #42 real-tile half — the assertion that would have caught the
    latitude-drift bug (#32) pre-merge.
    """
    tiles = _find_tiles()
    if len(tiles) < 2:
        print(f"  SKIP: need >=2 tiles, found {len(tiles)} in {DEM_CACHE}")
        return True

    # Group by latitude
    by_lat: dict[int, list[Path]] = {}
    for t in tiles:
        lat = _tile_lat(t)
        if lat is not None:
            by_lat.setdefault(lat, []).append(t)

    lats = sorted(by_lat)
    if len(lats) < 2:
        print(f"  SKIP: all tiles at same latitude ({lats}), need >=2 different latitudes")
        print("  (download a tile at a different latitude to enable this check)")
        return True

    # Pick one tile from each of 2 different latitudes
    pair = [by_lat[lats[0]][0], by_lat[lats[-1]][0]]
    print(f"  tiles: {pair[0].name} (lat {lats[0]}), {pair[1].name} (lat {lats[-1]})")

    from src.raster import normalize_dem
    from src.raster_io import RasterioRasterReader, RasterioReprojector

    reader = RasterioRasterReader()
    reprojector = RasterioReprojector()
    grids = [reader.read(str(p)) for p in pair]
    print(f"  source CRSs: {[g.crs for g in grids]}")

    mosaic = normalize_dem(grids, INTERNAL_CRS, reprojector=reprojector)
    pw = mosaic.transform.pixel_width
    ph = mosaic.transform.pixel_height
    print(f"  mosaic shape: {mosaic.values.shape}, pixel: {pw:.8f} x {ph:.8f}")

    # Uniform pixel size: width == height (within float tolerance)
    ok = True
    if abs(pw - ph) / max(pw, ph) > 1e-6:
        print(f"  FAIL: pixel_width ({pw}) != pixel_height ({ph}) — non-uniform grid")
        ok = False
    else:
        print("  uniform pixel size confirmed")

    if mosaic.values.size == 0:
        print("  FAIL: mosaic array is empty")
        ok = False

    print(f"  {'PASS' if ok else 'FAIL'}: multi-tile mosaic alignment")
    return ok


# -- (c) Cross-device SMB mover ----------------------------------------------


def check_mover() -> bool:
    """Move a temp file local -> NAS via src.storage.move_file, assert bytes intact."""
    if not NAS_MOUNT.is_dir():
        print(f"  SKIP: NAS not mounted at {NAS_MOUNT}")
        return True

    from src.storage import move_file

    payload = b"smoke-test-payload-" + os.urandom(32)
    expected_sha = _sha256(payload)

    # Write temp file locally
    with tempfile.NamedTemporaryFile(delete=False, suffix=".smoke") as f:
        f.write(payload)
        src_path = f.name

    # Destination on NAS
    dst_dir = NAS_MOUNT / "data" / "hydro-art" / "cache" / ".smoke-test"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_path = str(dst_dir / "smoke-mover-test.bin")

    print(f"  src: {src_path}")
    print(f"  dst: {dst_path}")

    ok = True
    try:
        move_file(src_path, dst_path)
        # Verify bytes arrived intact
        arrived = Path(dst_path).read_bytes()
        actual_sha = _sha256(arrived)
        if actual_sha != expected_sha:
            print(f"  FAIL: sha mismatch (expected {expected_sha[:16]}..., got {actual_sha[:16]}...)")
            ok = False
        else:
            print(f"  bytes intact: {len(arrived)} bytes, sha256 match")

        # Source should be removed after move
        if Path(src_path).exists():
            print("  WARN: source file still exists after move (expected removal)")
    except OSError as exc:
        print(f"  FAIL: OSError during move: {exc}")
        ok = False
    finally:
        # Clean up
        Path(dst_path).unlink(missing_ok=True)
        Path(src_path).unlink(missing_ok=True)
        try:
            dst_dir.rmdir()
        except OSError:
            pass

    print(f"  {'PASS' if ok else 'FAIL'}: cross-device SMB mover")
    return ok


# -- CLI ----------------------------------------------------------------------


def main() -> int:
    if os.environ.get("HYDRO_ART_REAL_DATA") != "1":
        print("Set HYDRO_ART_REAL_DATA=1 to run real-data smoke checks.")
        return 1

    ap = argparse.ArgumentParser(description="Real-data smoke harness")
    ap.add_argument("--warp", action="store_true", help="Non-identity EPSG:4269->5070 warp")
    ap.add_argument("--mosaic", action="store_true", help="Multi-tile mosaic alignment (#42)")
    ap.add_argument("--mover", action="store_true", help="Cross-device SMB mover")
    ap.add_argument("--all", action="store_true", help="Run all checks (epoch gate)")
    args = ap.parse_args()

    if not any([args.warp, args.mosaic, args.mover, args.all]):
        ap.print_help()
        return 1

    checks: list[tuple[str, bool]] = []

    if args.warp or args.all:
        print("[warp] Non-identity EPSG:4269 -> EPSG:5070")
        checks.append(("warp", check_warp()))
        print()

    if args.mosaic or args.all:
        print("[mosaic] Multi-tile alignment at different latitudes")
        checks.append(("mosaic", check_mosaic()))
        print()

    if args.mover or args.all:
        print("[mover] Cross-device SMB move (local -> NAS)")
        checks.append(("mover", check_mover()))
        print()

    # Summary
    print("=" * 40)
    all_ok = True
    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  {name}: {status}")
        if not ok:
            all_ok = False

    print(f"\n{'ALL PASSED' if all_ok else 'SOME FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
