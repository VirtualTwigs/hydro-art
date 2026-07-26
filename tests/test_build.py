"""Tests for the build.py entry point and pipeline skeleton (Task Group 3)."""

from build import main
from src.pipeline import PIPELINE_STAGES, Pipeline


def test_main_with_defaults_exits_zero(tmp_path):
    # Point at a nonexistent config so defaults are used deterministically.
    assert main(["--config", str(tmp_path / "none.yaml")]) == 0


def test_main_with_invalid_region_exits_nonzero(tmp_path):
    assert main(["--config", str(tmp_path / "none.yaml"), "--region", "Idaho"]) == 1


def test_pipeline_stage_order_matches_prd_section_8():
    assert Pipeline().stage_names == tuple(s.name for s in PIPELINE_STAGES)
    assert Pipeline().stage_names[0] == "download"
    assert Pipeline().stage_names[-1] == "export"
