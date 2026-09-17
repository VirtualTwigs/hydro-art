"""Determinism verdict + golden-hash registry (roadmap #39/#40, pure core).

The determinism verifier (``tools/verify_determinism.py``) renders a region
**twice** through the real GDAL-backed :class:`~src.pipeline.Pipeline` (and, since
#40, optionally fingerprints the region's DEM mosaic) and needs to answer these
questions from the resulting digests:

1. **Run-to-run**: did the two renders on this machine produce the same SVG bytes?
   (the deterministic-output invariant the whole epoch exists to make provable).
2. **Against golden**: does the render match the committed per-region golden hash
   (roadmap #40's fixture)? — this also catches drift introduced by a code
   change, not just run-to-run flakiness. A region with no recorded golden yet is
   a soft "record me" prompt, not a failure.
3. **DEM mosaic** (#40): does the region's DEM mosaic checksum
   (``src.raster.grid_checksum`` of ``normalize_dem(...).base``) match its golden?
   This fingerprints the real GDAL warp/mosaic path the offline fakes only
   simulate. It is a **same-host regression** (GDAL/PROJ version-sensitive),
   unlike the pure-Python, cross-host SVG sha.

This module is the **pure** half of that: load/merge a golden registry, evaluate
the verdict, and format it for the CLI. It imports only stdlib (plus
:data:`src.config.SUPPORTED_REGIONS` for boundary validation), so it runs in the
offline suite; the double-render + DEM checksum themselves are the non-offline
part in ``tools/``.

Registry schema (``tests/fixtures/golden/registry.json``)::

    {"Washington/clark": {"svg_sha256": "<64 hex>", "dem_mosaic_sha256": "<64 hex>"}}

``dem_mosaic_sha256`` is optional; a bare string value is also accepted as an
SVG-only golden (a #39-era flat entry still loads).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.config import SUPPORTED_REGIONS

__all__ = [
    "DeterminismError",
    "DeterminismVerdict",
    "Golden",
    "dump_registry",
    "evaluate",
    "format_verdict",
    "load_registry",
    "lookup_golden",
    "record_golden",
    "registry_key",
]

_HEX = set("0123456789abcdef")


class DeterminismError(ValueError):
    """A determinism registry/evaluation was called with invalid inputs."""


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in _HEX for c in value.lower())
    )


@dataclass(frozen=True)
class Golden:
    """A committed golden entry: the SVG sha and an optional DEM mosaic sha."""

    svg_sha256: str
    dem_mosaic_sha256: str | None = None


def registry_key(region: str, county: str | None = None) -> str:
    """Return the registry key for a region (optionally a county within it).

    Region is validated against :data:`SUPPORTED_REGIONS` (case-insensitive,
    normalized to the canonical name) so a typo can't silently record a golden
    under a bogus key. The county is normalized to lowercase; the key is
    ``"<region>"`` or ``"<region>/<county>"``.
    """
    canonical = {r.lower(): r for r in SUPPORTED_REGIONS}
    key = region.strip().lower()
    if key not in canonical:
        raise DeterminismError(
            f"Unknown region {region!r}; expected one of "
            f"{', '.join(sorted(SUPPORTED_REGIONS))}."
        )
    base = canonical[key]
    if county:
        return f"{base}/{county.strip().lower()}"
    return base


def _parse_entry(key: str, value: object, path: Path) -> Golden:
    """Parse one registry value (object or bare-string) into a :class:`Golden`."""
    if isinstance(value, str):
        if not _is_sha256(value):
            raise DeterminismError(
                f"Golden registry {path} entry {key!r} is not a 64-hex sha256."
            )
        return Golden(svg_sha256=value.lower())
    if isinstance(value, dict):
        svg = value.get("svg_sha256")
        if not _is_sha256(svg):
            raise DeterminismError(
                f"Golden registry {path} entry {key!r} is missing a 64-hex "
                "'svg_sha256'."
            )
        dem = value.get("dem_mosaic_sha256")
        if dem is not None and not _is_sha256(dem):
            raise DeterminismError(
                f"Golden registry {path} entry {key!r} 'dem_mosaic_sha256' is not "
                "a 64-hex sha256."
            )
        return Golden(
            svg_sha256=svg.lower(),
            dem_mosaic_sha256=dem.lower() if dem is not None else None,
        )
    raise DeterminismError(
        f"Golden registry {path} entry {key!r} must be a sha256 string or object."
    )


def load_registry(path: str | Path) -> dict[str, Golden]:
    """Load a ``{key: Golden}`` golden registry from JSON.

    A missing file is an empty registry (first run for the whole project), not an
    error. Each value is either an object ``{"svg_sha256": ..,
    "dem_mosaic_sha256"?: ..}`` or a bare 64-hex sha string (svg-only).
    """
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DeterminismError(f"Golden registry {p} is not valid JSON: {exc}.") from exc
    if not isinstance(data, dict):
        raise DeterminismError(f"Golden registry {p} must be a JSON object.")
    return {str(key): _parse_entry(str(key), value, p) for key, value in data.items()}


def dump_registry(registry: Mapping[str, Golden]) -> dict[str, dict[str, str]]:
    """Serialize a ``{key: Golden}`` registry to a JSON-ready dict.

    The DEM half is omitted when unrecorded, so an svg-only golden stays compact.
    """
    out: dict[str, dict[str, str]] = {}
    for key, golden in registry.items():
        entry = {"svg_sha256": golden.svg_sha256}
        if golden.dem_mosaic_sha256 is not None:
            entry["dem_mosaic_sha256"] = golden.dem_mosaic_sha256
        out[key] = entry
    return out


def lookup_golden(registry: Mapping[str, Golden], key: str) -> Golden | None:
    """Return the recorded golden for ``key``, or ``None`` if unrecorded."""
    return registry.get(key)


@dataclass(frozen=True)
class DeterminismVerdict:
    """The outcome of comparing repeated renders against each other + golden.

    Attributes:
        key: The registry key evaluated (region or region/county).
        run_shas: The ``svg_sha256`` of each render, in order.
        golden_sha: The recorded SVG golden, or ``None`` if unrecorded.
        run_to_run_ok: True iff every run produced the same SVG sha.
        golden_ok: True/False iff an SVG golden exists and all runs match it;
            ``None`` when no SVG golden is recorded yet.
        dem_sha: The DEM mosaic checksum computed this run, or ``None`` if not
            checked.
        golden_dem_sha: The recorded DEM golden, or ``None`` if unrecorded.
        dem_ok: True/False iff a DEM golden exists, a ``dem_sha`` was supplied,
            and they match; ``None`` when the DEM was not checked or is unrecorded.
    """

    key: str
    run_shas: tuple[str, ...]
    golden_sha: str | None
    run_to_run_ok: bool
    golden_ok: bool | None
    dem_sha: str | None = None
    golden_dem_sha: str | None = None
    dem_ok: bool | None = None

    @property
    def needs_recording(self) -> bool:
        """Stable run-to-run but some golden half is missing ("record me")."""
        if not self.run_to_run_ok:
            return False
        svg_missing = self.golden_sha is None
        dem_missing = self.dem_sha is not None and self.golden_dem_sha is None
        return svg_missing or dem_missing

    @property
    def ok(self) -> bool:
        """Overall pass: stable run-to-run and no golden half mismatches."""
        return (
            self.run_to_run_ok
            and self.golden_ok is not False
            and self.dem_ok is not False
        )


def evaluate(
    key: str,
    run_shas: Sequence[str],
    registry: Mapping[str, Golden],
    *,
    dem_sha: str | None = None,
) -> DeterminismVerdict:
    """Evaluate repeated-render shas for ``key`` against each other and golden.

    ``dem_sha`` (optional, #40) is the region's DEM mosaic checksum this run; when
    supplied it is compared against the recorded DEM golden.

    Raises:
        DeterminismError: If fewer than two runs are supplied, any SVG sha is not a
            64-hex digest, or ``dem_sha`` (when given) is not a 64-hex digest.
    """
    shas = tuple(run_shas)
    if len(shas) < 2:
        raise DeterminismError(
            "evaluate needs at least two render shas to check run-to-run determinism."
        )
    for sha in shas:
        if not _is_sha256(sha):
            raise DeterminismError(f"Render sha {sha!r} is not a 64-hex sha256.")
    if dem_sha is not None and not _is_sha256(dem_sha):
        raise DeterminismError(f"DEM sha {dem_sha!r} is not a 64-hex sha256.")

    run_to_run_ok = len(set(shas)) == 1
    golden = registry.get(key)
    golden_sha = golden.svg_sha256 if golden else None
    golden_dem_sha = golden.dem_mosaic_sha256 if golden else None

    golden_ok: bool | None
    if golden_sha is None:
        golden_ok = None
    else:
        golden_ok = all(sha == golden_sha for sha in shas)

    dem_ok: bool | None
    if dem_sha is None or golden_dem_sha is None:
        dem_ok = None
    else:
        dem_ok = dem_sha == golden_dem_sha

    return DeterminismVerdict(
        key=key,
        run_shas=shas,
        golden_sha=golden_sha,
        run_to_run_ok=run_to_run_ok,
        golden_ok=golden_ok,
        dem_sha=dem_sha,
        golden_dem_sha=golden_dem_sha,
        dem_ok=dem_ok,
    )


def record_golden(
    registry: Mapping[str, Golden], verdict: DeterminismVerdict
) -> dict[str, Golden]:
    """Return a new registry with ``verdict``'s stable shas recorded for its key.

    Only a run-to-run-stable render may be recorded (recording a flaky render
    would bake in noise). The stable SVG sha is always recorded; the DEM mosaic
    sha is recorded when this run computed one, otherwise an existing DEM golden
    for the key is preserved (halves merge, never clobber).

    Raises:
        DeterminismError: If the render is not run-to-run stable.
    """
    if not verdict.run_to_run_ok:
        raise DeterminismError(
            f"Refusing to record a run-to-run-unstable render for {verdict.key!r}."
        )
    updated = dict(registry)
    existing = updated.get(verdict.key)
    dem = verdict.dem_sha
    if dem is None and existing is not None:
        dem = existing.dem_mosaic_sha256
    updated[verdict.key] = Golden(svg_sha256=verdict.run_shas[0], dem_mosaic_sha256=dem)
    return updated


def format_verdict(verdict: DeterminismVerdict) -> str:
    """Render a human-readable one-block report of the verdict."""
    lines = [f"determinism: {verdict.key}"]
    if verdict.run_to_run_ok:
        lines.append(f"  run-to-run: OK ({verdict.run_shas[0]})")
    else:
        lines.append("  run-to-run: DRIFT — renders differ:")
        for i, sha in enumerate(verdict.run_shas, start=1):
            lines.append(f"    run {i}: {sha}")
    if verdict.golden_sha is None:
        if verdict.run_to_run_ok:
            lines.append("  golden: none recorded — record this run with --record")
        else:
            lines.append("  golden: none recorded (fix run-to-run drift first)")
    elif verdict.golden_ok:
        lines.append(f"  golden: MATCH ({verdict.golden_sha})")
    else:
        lines.append("  golden: MISMATCH")
        lines.append(f"    expected: {verdict.golden_sha}")
        lines.append(f"    actual:   {verdict.run_shas[0]}")

    # DEM mosaic line (#40) — only shown once a DEM checksum was involved.
    if verdict.dem_sha is not None or verdict.golden_dem_sha is not None:
        if verdict.dem_sha is None:
            lines.append("  dem: not checked (golden recorded)")
        elif verdict.golden_dem_sha is None:
            lines.append(
                "  dem: none recorded — record this run with --record "
                f"({verdict.dem_sha})"
            )
        elif verdict.dem_ok:
            lines.append(f"  dem: MATCH ({verdict.golden_dem_sha})")
        else:
            lines.append("  dem: MISMATCH")
            lines.append(f"    expected: {verdict.golden_dem_sha}")
            lines.append(f"    actual:   {verdict.dem_sha}")

    lines.append(f"  verdict: {'PASS' if verdict.ok else 'FAIL'}")
    return "\n".join(lines)
