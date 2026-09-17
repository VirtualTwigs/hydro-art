"""Tests for the local job runner core (roadmap #27, Task Group 1).

Fully offline: a fake pipeline + an inline executor stand in for the real
`Pipeline`, so no sockets, network, GDAL, or datasets are touched.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.config import ConfigError, Settings
from src.jobs import (
    FAILED,
    SUCCEEDED,
    Job,
    JobRunner,
    settings_from_payload,
)


class InlineExecutor:
    """Runs submitted callables synchronously so jobs finish before submit returns."""

    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


class FakePipeline:
    """Stands in for `Pipeline`; records the settings it ran and returns a fake ctx."""

    def __init__(self, *, exc: Exception | None = None):
        self._exc = exc
        self.ran_with: Settings | None = None

    def run(self, settings: Settings):
        self.ran_with = settings
        if self._exc is not None:
            raise self._exc
        return SimpleNamespace(
            artifacts={
                "export_paths": {"svg": "output/oregon.svg"},
                "svg_sha256": "deadbeef",
            }
        )


def _runner(pipeline):
    return JobRunner(pipeline, executor=InlineExecutor())


def test_settings_from_payload_maps_known_keys():
    settings = settings_from_payload(
        {"region": "Oregon", "color_by": "single", "single_color": "#123456",
         "width_by": "flow", "months": "may-sep"}
    )
    assert settings.regions == ("Oregon",)
    assert settings.color_by == "single"
    assert settings.width_by == "flow"
    assert settings.months == (5, 6, 7, 8, 9)


def test_settings_from_payload_ignores_unknown_keys():
    settings = settings_from_payload({"region": "Oregon", "bogus": "x", "__proto__": 1})
    assert settings.regions == ("Oregon",)


def test_settings_from_payload_invalid_raises_config_error():
    with pytest.raises(ConfigError):
        settings_from_payload({"region": "Atlantis"})


def test_submit_runs_pipeline_and_succeeds():
    pipeline = FakePipeline()
    runner = _runner(pipeline)
    job_id = runner.submit({"region": "Oregon"})
    job = runner.status(job_id)
    assert isinstance(job, Job)
    assert job.state == SUCCEEDED
    assert job.outputs == {"svg": "output/oregon.svg"}
    assert job.sha256 == "deadbeef"
    assert pipeline.ran_with.regions == ("Oregon",)


def test_pipeline_error_marks_job_failed_with_message():
    pipeline = FakePipeline(exc=ConfigError("months needs monthly discharge"))
    runner = _runner(pipeline)
    job_id = runner.submit({"region": "Oregon"})
    job = runner.status(job_id)
    assert job.state == FAILED
    assert "monthly discharge" in job.error


def test_submit_invalid_payload_raises_before_scheduling():
    pipeline = FakePipeline()
    runner = _runner(pipeline)
    with pytest.raises(ConfigError):
        runner.submit({"region": "Atlantis"})
    assert pipeline.ran_with is None


def test_status_unknown_id_raises_keyerror():
    runner = _runner(FakePipeline())
    with pytest.raises(KeyError):
        runner.status("nope")


def test_to_dict_is_json_serializable_envelope():
    runner = _runner(FakePipeline())
    job_id = runner.submit({"region": "Oregon"})
    envelope = runner.to_dict(runner.status(job_id))
    assert envelope["id"] == job_id
    assert envelope["state"] == SUCCEEDED
    assert envelope["outputs"] == {"svg": "output/oregon.svg"}
    assert envelope["sha256"] == "deadbeef"
    assert envelope["error"] is None
