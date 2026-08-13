"""Tests for the serve.py cache-dir resolver (#27 Run-pipeline robustness).

serve.py imports only stdlib + rich + the GDAL-free src.jobs/src.server, so this
runs in the offline suite; the heavy Pipeline is imported lazily inside main().
"""

from pathlib import Path

from serve import _resolve_cache_dir


def test_explicit_cache_dir_always_wins(tmp_path):
    chosen = _resolve_cache_dir(
        str(tmp_path / "custom"), nas_dir="/nope/data/incoming", local_dir="cache"
    )
    assert chosen == Path(str(tmp_path / "custom"))


def test_prefers_nas_when_mounted(tmp_path):
    # NAS is "mounted" when the incoming dir's parent exists.
    nas = tmp_path / "home" / "data" / "incoming"
    nas.parent.mkdir(parents=True)
    chosen = _resolve_cache_dir(None, nas_dir=str(nas), local_dir=str(tmp_path / "cache"))
    assert chosen == nas


def test_falls_back_to_local_when_nas_unmounted(tmp_path):
    # Parent of the incoming dir does not exist → NAS not mounted → local.
    nas = tmp_path / "unmounted" / "data" / "incoming"
    local = tmp_path / "cache"
    chosen = _resolve_cache_dir(None, nas_dir=str(nas), local_dir=str(local))
    assert chosen == local
