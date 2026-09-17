#!/usr/bin/env python3
"""Run N end-to-end builds with random state/county/style combos.

Usage:  python tools/random_e2e.py [--runs N]  (default 10)
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYTHON = str(REPO / ".venv" / "bin" / "python")

# -- option pools --------------------------------------------------------

STATES = ["Oregon", "Washington", "California", "Idaho"]

# Counties per state (Census NAME values)
COUNTIES: dict[str, list[str]] = {}  # filled dynamically below

COLOR_MODES = ["watershed", "single"]  # skip elevation (needs DEM tools/ path)
WIDTH_MODES = ["uniform", "flow"]
STREAM_METHODS = ["strahler", "shreve", "hack"]
HUC_LEVELS = ["HUC2", "HUC4", "HUC6", "HUC8"]
GLOW_MODES = ["vector", "blur"]
OUTPUTS = ["svg", "png"]
PNG_SIZES = [512, 1024, 2048]  # draft tiers for speed
WATERBODY_PRESETS = ["screen", "print-state", "print-county"]
POINT_PRESETS = ["screen", "print-state", "print-county"]
AREAL_PRESETS = ["screen", "print-state", "print-county"]
WIDTH_PRESETS = ["state", "basin", "watershed"]
SINGLE_COLORS = ["#00ffff", "#ff00ff", "#00ff88", "#ffaa00"]


def load_counties() -> None:
    """Read county names from the Census shapefile."""
    try:
        import geopandas as gpd  # noqa: WPS433

        fips = {"Oregon": "41", "Washington": "53", "California": "06", "Idaho": "16"}
        gdf = gpd.read_file("/tmp/counties_shp/cb_2023_us_county_500k.shp")
        for state, fp in fips.items():
            COUNTIES[state] = sorted(gdf[gdf.STATEFP == fp]["NAME"].tolist())
    except Exception:
        # Fallback: a few known counties per state
        COUNTIES.update(
            {
                "Oregon": ["Multnomah", "Lane", "Deschutes", "Jackson", "Clackamas"],
                "Washington": ["Clark", "King", "Pierce", "Spokane", "Whatcom"],
                "California": ["Los Angeles", "Humboldt", "Shasta", "San Diego"],
                "Idaho": ["Ada", "Boise", "Kootenai", "Bonneville"],
            }
        )


def random_config(run_id: int) -> tuple[list[str], str]:
    """Return (build.py argv, human-readable description)."""
    state = random.choice(STATES)
    county = random.choice(COUNTIES[state])

    color_by = random.choice(COLOR_MODES)
    width_by = random.choice(WIDTH_MODES)
    glow = random.random() < 0.5
    stream = random.choice(STREAM_METHODS)
    huc = random.choice(HUC_LEVELS)
    out_fmt = random.choice(OUTPUTS)

    args = [
        PYTHON, str(REPO / "build.py"),
        "--region", state,
        "--county", county,
        "--palette", "neon",
        "--color-by", color_by,
        "--width-by", width_by,
        "--stream-method", stream,
        "--huc-level", huc,
        "--output", out_fmt,
    ]

    desc_parts = [f"{state}/{county}", f"color={color_by}", f"width={width_by}"]

    if out_fmt == "png":
        ps = random.choice(PNG_SIZES)
        args += ["--png-size", str(ps)]
        desc_parts.append(f"png@{ps}")

    if color_by == "single":
        sc = random.choice(SINGLE_COLORS)
        args += ["--single-color", sc]
        desc_parts.append(f"single={sc}")

    if glow:
        gm = random.choice(GLOW_MODES)
        args += ["--glow", "--glow-mode", gm]
        desc_parts.append(f"glow={gm}")

    if width_by == "flow":
        wp = random.choice(WIDTH_PRESETS)
        args += ["--width-preset", wp]
        desc_parts.append(f"width_preset={wp}")

    # Randomly enable feature layers (30% chance each)
    if random.random() < 0.3:
        wp = random.choice(WATERBODY_PRESETS)
        args += ["--waterbody-preset", wp]
        desc_parts.append(f"waterbody={wp}")

    if random.random() < 0.3:
        pp = random.choice(POINT_PRESETS)
        args += ["--point-feature-preset", pp]
        desc_parts.append(f"points={pp}")

    if random.random() < 0.3:
        ap = random.choice(AREAL_PRESETS)
        args += ["--areal-feature-preset", ap]
        desc_parts.append(f"areal={ap}")

    desc_parts.append(f"stream={stream}")
    desc_parts.append(f"huc={huc}")

    desc = f"[Run {run_id:02d}] {' | '.join(desc_parts)}"
    return args, desc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=None)
    opts = parser.parse_args()

    if opts.seed is not None:
        random.seed(opts.seed)
    else:
        seed = random.randint(0, 2**32 - 1)
        random.seed(seed)
        print(f"Random seed: {seed}")

    load_counties()

    results: list[dict] = []
    for i in range(1, opts.runs + 1):
        args, desc = random_config(i)
        print(f"\n{'='*72}")
        print(desc)
        print(f"CMD: {' '.join(args)}")
        print(f"{'='*72}")

        t0 = time.time()
        try:
            proc = subprocess.run(
                args, cwd=str(REPO), capture_output=True, text=True, timeout=300,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.time() - t0
            print(f"  → TIMEOUT ({elapsed:.1f}s)")
            results.append(
                {
                    "run": i,
                    "desc": desc,
                    "status": "TIMEOUT",
                    "elapsed_s": round(elapsed, 1),
                    "exit_code": -1,
                }
            )
            continue
        elapsed = time.time() - t0

        status = "PASS" if proc.returncode == 0 else "FAIL"
        print(f"  → {status} ({elapsed:.1f}s, exit {proc.returncode})")
        if proc.returncode != 0:
            # Print last 20 lines of stderr
            err_lines = proc.stderr.strip().splitlines()[-20:]
            for line in err_lines:
                print(f"    {line}")

        results.append(
            {
                "run": i,
                "desc": desc,
                "status": status,
                "elapsed_s": round(elapsed, 1),
                "exit_code": proc.returncode,
            }
        )

    # Summary
    print(f"\n{'='*72}")
    print("SUMMARY")
    print(f"{'='*72}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total_time = sum(r["elapsed_s"] for r in results)
    for r in results:
        print(f"  {r['status']}  {r['desc']}  ({r['elapsed_s']:.1f}s)")
    print(f"\n{passed}/{opts.runs} passed, {failed} failed, {total_time:.0f}s total")


if __name__ == "__main__":
    main()
