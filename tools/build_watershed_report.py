"""Parametrized watershed-report builder (roadmap #54).

Thin CLI over ``tools/report_common.py``: given a watershed (parent HUC4 + its
WBDHU12 codes + a name + a year span), it assembles the year-over-year PRISM flow
series, optionally attaches a USGS gauge (model-vs-gauge validation, #50) and a
climate index (ENSO/PDO teleconnection, #51), and writes the full figure set to
``notebooks/figures/``. A JSON metrics summary is printed to stdout.

    # Salmon Creek, validated against its basin gauge over the gauge's record:
    python -m tools.build_watershed_report \\
        --huc4 1708 --huc12 170800030102 170800030103 \\
        --name "Salmon Creek" --start 1944 --end 1989 \\
        --gauge 14212000 --index oni

Needs the PRISM grids staged (``tools/prism_fetch.py``) and reuses the year-over-
year clip/network caches. Heavy GIS + matplotlib live in ``report_common``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.climate_index import ClimateIndexProvider
from tools.historical_flow import DEFAULT_ROOT
from tools.nwis_gauge import GaugeProvider
from tools.report_common import FIG_DIR, build_report, load_watershed_series


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--huc4", default="1708", help="Parent NHDPlus HR HUC4 basin.")
    ap.add_argument("--huc12", nargs="+", default=["170800030102", "170800030103"],
                    help="WBDHU12 codes making up the watershed.")
    ap.add_argument("--name", default="Salmon Creek", help="Watershed label.")
    ap.add_argument("--start", type=int, default=1944)
    ap.add_argument("--end", type=int, default=1989)
    ap.add_argument("--gauge", default=None,
                    help="USGS NWIS site id for model-vs-gauge validation (#50).")
    ap.add_argument("--index", default="oni", choices=["oni", "pdo"],
                    help="Climate index for the teleconnection panel (#51).")
    ap.add_argument("--no-index", action="store_true",
                    help="Skip the climate-index teleconnection panel.")
    ap.add_argument("--no-creative", action="store_true",
                    help="Skip the #76 creative-analytics panels (timing drift, "
                         "analog years, record book, decade FDC, composites).")
    ap.add_argument("--root", default=DEFAULT_ROOT,
                    help="External root holding prism/, nwis/, climate/ snapshots.")
    ap.add_argument("--min-order", type=int, default=1)
    ap.add_argument("--climate-source", choices=["nclimgrid", "prism"],
                    default="nclimgrid",
                    help="Climate source: nclimgrid (public domain, default) or "
                         "prism (legacy, rights-gated).")
    ap.add_argument("--out-dir", default=str(FIG_DIR))
    args = ap.parse_args()

    print(f"loading {args.name} ({args.start}–{args.end}) ...")
    ws = load_watershed_series(
        args.huc4, args.huc12, args.name, args.start, args.end,
        root=args.root, min_order=args.min_order,
        climate_source=args.climate_source,
    )
    print(f"  {ws.n} reaches; outlet reach idx {ws.outlet_idx}; "
          f"peak month {ws.peak_month + 1}")

    gauge_obs = None
    gauge_loc = None
    if args.gauge:
        print(f"fetching gauge {args.gauge} ...")
        prov = GaugeProvider(args.gauge, args.root)
        obs = prov.monthly_means(args.start, args.end)
        gauge_obs = obs
        gauge_loc = prov.location()
        print(f"  gauge: {len(obs)} years with observed monthly means; "
              f"site at lat {gauge_loc[0]:.4f}, lon {gauge_loc[1]:.4f} "
              f"({gauge_loc[2]})")

    index_by_year = None
    if not args.no_index:
        print(f"fetching climate index {args.index} ...")
        idx = ClimateIndexProvider(args.index, args.root).index_by_year(
            args.start, args.end)
        index_by_year = idx
        print(f"  index: {len(idx)} years")

    summary = build_report(
        ws, gauge_obs=gauge_obs, gauge_loc=gauge_loc, index_by_year=index_by_year,
        index_name=args.index.upper(), creative=not args.no_creative,
        out_dir=Path(args.out_dir),
    )
    print(f"\nwrote figures to {args.out_dir}/")
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
