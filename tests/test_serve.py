"""Tests for the serve.py cache-dir resolver (#27 Run-pipeline robustness).

serve.py imports only stdlib + rich + the GDAL-free src.jobs/src.server, so this
runs in the offline suite; the heavy Pipeline is imported lazily inside main().
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import serve as serve_module
from serve import _ensure_output_root, _resolve_cache_dir, _serve_roots
from src.storage import EXTERNAL_ROOT_ENV, StorageRoots


class FakeConsole:
    def __init__(self):
        self.messages = []

    def print(self, message):
        self.messages.append(message)


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


def test_serve_roots_default_keeps_local_datasets_output(monkeypatch, tmp_path):
    # No external root → today's serve behavior: NAS-or-local cache (here local,
    # NAS unmounted), datasets/output stay local.
    monkeypatch.delenv(EXTERNAL_ROOT_ENV, raising=False)
    roots = _serve_roots(external_root=None, cache_dir=str(tmp_path / "c"))
    assert roots.cache == Path(str(tmp_path / "c"))
    assert roots.datasets == Path("datasets")
    assert roots.output == Path("output")
    assert roots.using_external is False


def test_serve_roots_external_root_resolves_all(monkeypatch, tmp_path):
    monkeypatch.delenv(EXTERNAL_ROOT_ENV, raising=False)
    drive = tmp_path / "drive"
    roots = _serve_roots(
        external_root=str(drive), cache_dir=None, available=lambda _p: True
    )
    assert roots.cache == drive / "cache"
    assert roots.datasets == drive / "datasets"
    assert roots.output == drive / "output"
    assert roots.using_external is True


def test_serve_roots_external_root_from_env(monkeypatch, tmp_path):
    drive = tmp_path / "drive"
    monkeypatch.setenv(EXTERNAL_ROOT_ENV, str(drive))
    roots = _serve_roots(
        external_root=None, cache_dir=None, available=lambda _p: True
    )
    assert roots.output == drive / "output"


def test_ensure_output_root_creates_configured_directory(tmp_path):
    roots = StorageRoots(
        cache=tmp_path / "cache",
        datasets=tmp_path / "datasets",
        output=tmp_path / "output",
        external_root=None,
        using_external=False,
    )

    result = _ensure_output_root(roots, FakeConsole())

    assert result == roots
    assert roots.output.is_dir()


def test_ensure_output_root_falls_back_when_configured_path_is_unusable(tmp_path):
    unusable = tmp_path / "not-a-directory"
    unusable.write_text("occupied")
    fallback = tmp_path / "output-local"
    console = FakeConsole()
    roots = StorageRoots(
        cache=tmp_path / "cache",
        datasets=tmp_path / "datasets",
        output=unusable,
        external_root=tmp_path,
        using_external=True,
    )

    result = _ensure_output_root(roots, console, fallback=fallback)

    assert result.output == fallback
    assert result.cache == roots.cache
    assert result.datasets == roots.datasets
    assert result.external_root == roots.external_root
    assert result.using_external is True
    assert fallback.is_dir()
    assert console.messages == [
        "[yellow]NAS output unreachable; using output_local/[/]"
    ]


@pytest.mark.parametrize("error_type", [PermissionError, OSError])
def test_main_shares_fallback_output_with_all_consumers(
    monkeypatch, tmp_path, error_type
):
    """Startup must use the fallback for rendering, order storage, and serving."""
    monkeypatch.chdir(tmp_path)
    roots = StorageRoots(
        cache=tmp_path / "cache",
        datasets=tmp_path / "datasets",
        output=tmp_path / "unavailable-output",
        external_root=None,
        using_external=False,
    )
    original_mkdir = Path.mkdir

    def mkdir(path, *args, **kwargs):
        if path == roots.output:
            raise error_type("output unavailable")
        return original_mkdir(path, *args, **kwargs)

    captured = {}

    def pipeline(**kwargs):
        captured["pipeline"] = kwargs
        return object()

    def order_store(path, console):
        captured["orders"] = path
        return object()

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(serve_module, "_serve_roots", lambda **kwargs: roots)
    monkeypatch.setitem(
        sys.modules, "src.pipeline", SimpleNamespace(Pipeline=pipeline)
    )
    monkeypatch.setattr(serve_module, "JobRunner", lambda pipeline: object())
    monkeypatch.setattr(serve_module, "_build_order_store", order_store)
    monkeypatch.setattr(
        serve_module, "serve", lambda runner, **kwargs: captured.update(server=kwargs)
    )

    assert serve_module.main([]) == 0
    assert captured["pipeline"]["output_dir"] == Path("output_local")
    assert captured["orders"] == Path("output_local/orders")
    assert captured["server"]["output_root"] == Path("output_local")
    assert (tmp_path / "output_local").is_dir()
