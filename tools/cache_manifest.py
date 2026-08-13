"""Portable cache-manifest CLI (roadmap #21, offline-packaging slice).

Build/write, verify, and diff a *portable cache manifest* over a real (e.g. NAS)
cache so a cache can be audited, shipped between machines, and reconciled offline.
All the logic lives in the pure, offline :mod:`src.manifest`; this wrapper only
builds the ``Settings`` + ``Cache`` and prints results.

Usage::

    # Build a manifest for one or more regions and write it to disk.
    python tools/cache_manifest.py write --region Oregon \
        --cache-dir /Volumes/home/data/incoming --out oregon.manifest.json

    # Verify a saved manifest against a (possibly moved) cache directory.
    python tools/cache_manifest.py verify oregon.manifest.json --cache-dir ./cache

    # Reconcile two saved manifests (old -> new).
    python tools/cache_manifest.py diff old.manifest.json new.manifest.json

``write`` exits ``0`` on success (``--strict`` makes a required file with no cached
metadata a hard error → ``1``). ``verify`` exits ``0`` only when every entry is
present and intact, ``diff`` only when the two manifests are in sync. Reads a real
cache, so it is not part of the offline test suite.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from src.cache import Cache
from src.cli import resolve_settings
from src.config import ConfigError
from src.manifest import (
    ManifestError,
    diff_manifests,
    format_diff,
    format_verification,
    manifest_for_settings,
    read_manifest,
    verify_manifest,
    write_manifest,
)


def _cmd_write(args: argparse.Namespace) -> int:
    forwarded = ["--region", *args.region, "--config", args.config]
    try:
        settings = resolve_settings(forwarded)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    cache = Cache(args.cache_dir)
    try:
        manifest = manifest_for_settings(cache, settings, strict=args.strict)
    except ManifestError as exc:
        print(f"Manifest error: {exc}", file=sys.stderr)
        return 1
    write_manifest(manifest, args.out)
    total_bytes = sum(e.size for e in manifest.entries)
    print(f"Wrote {len(manifest.entries)} entry(ies), {total_bytes} bytes -> {args.out}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    try:
        manifest = read_manifest(args.manifest)
    except ManifestError as exc:
        print(f"Manifest error: {exc}", file=sys.stderr)
        return 1
    verification = verify_manifest(manifest, args.cache_dir)
    print(format_verification(verification))
    return 0 if verification.is_complete else 1


def _cmd_diff(args: argparse.Namespace) -> int:
    try:
        old = read_manifest(args.old)
        new = read_manifest(args.new)
    except ManifestError as exc:
        print(f"Manifest error: {exc}", file=sys.stderr)
        return 1
    diff = diff_manifests(old, new)
    print(format_diff(diff))
    return 0 if diff.is_synced else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build/verify/diff portable cache manifests (roadmap #21)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    write = sub.add_parser("write", help="Build a manifest for region(s) and write it.")
    write.add_argument("--region", nargs="+", required=True, help="Region(s) to cover.")
    write.add_argument(
        "--cache-dir", required=True, help="Cache root to read (may be a NAS mount)."
    )
    write.add_argument("--out", default="manifest.json", help="Manifest output path.")
    write.add_argument("--config", default="config.yaml", help="YAML config path.")
    write.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any required file lacks cached metadata.",
    )
    write.set_defaults(func=_cmd_write)

    verify = sub.add_parser("verify", help="Verify a cache dir against a saved manifest.")
    verify.add_argument("manifest", help="Manifest file to verify against.")
    verify.add_argument("--cache-dir", required=True, help="Cache root to check.")
    verify.set_defaults(func=_cmd_verify)

    diff = sub.add_parser("diff", help="Diff two saved manifests (old -> new).")
    diff.add_argument("old", help="Old manifest file.")
    diff.add_argument("new", help="New manifest file.")
    diff.set_defaults(func=_cmd_diff)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
