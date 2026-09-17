"""Local job runner core for the web control surface (roadmap #27).

Turns a structured JSON payload of config selections into a validated
:class:`~src.config.Settings` and runs an **injected** pipeline off the request
thread, tracking a simple job lifecycle so the browser can poll for the produced
artifact. The pipeline is duck-typed (anything with ``run(settings) -> ctx`` whose
``ctx.artifacts`` is a mapping), so this module imports only stdlib + ``src.config``:
it stays GDAL-free and the whole thing is exercised offline with a fake pipeline and
an inline executor. The real, heavy :class:`~src.pipeline.Pipeline` is wired in by the
thin ``serve.py`` entry point, never here.

Security: the payload is a **whitelisted mapping of known config keys** fed through the
existing ``build_settings`` boundary validation — the emitted CLI string is never
shell-executed.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.config import DEFAULTS, Settings, build_settings

__all__ = [
    "FAILED",
    "PENDING",
    "RUNNING",
    "SUCCEEDED",
    "Job",
    "JobRunner",
    "settings_from_payload",
]

#: Job lifecycle states.
PENDING = "pending"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"

#: Payload keys accepted from the browser — exactly the recognized config keys.
#: Anything else (including ``__proto__``-style noise) is dropped before validation.
ACCEPTED_KEYS: frozenset[str] = frozenset(DEFAULTS)


class PipelineLike(Protocol):
    """Anything the runner can drive: ``run`` returns a ctx exposing ``artifacts``."""

    def run(self, settings: Settings) -> Any: ...


class ExecutorLike(Protocol):
    """Anything that can schedule ``fn(*args)`` (e.g. a ``ThreadPoolExecutor``)."""

    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> Any: ...


def settings_from_payload(payload: Mapping[str, Any]) -> Settings:
    """Validate a browser payload into :class:`Settings`.

    Copies only keys in :data:`ACCEPTED_KEYS` from ``payload`` and delegates to
    :func:`~src.config.build_settings`, which fills defaults and validates every
    field at the boundary.

    Raises:
        ConfigError: If any provided value is invalid.
    """
    values = {key: payload[key] for key in payload if key in ACCEPTED_KEYS}
    return build_settings(values)


@dataclass
class Job:
    """A single render job's mutable lifecycle record."""

    id: str
    state: str = PENDING
    error: str | None = None
    outputs: dict[str, str] = field(default_factory=dict)
    sha256: str | None = None


class JobRunner:
    """Submits render jobs to an injected pipeline and tracks their status.

    Args:
        pipeline: The pipeline to run (injected; real one wired in ``serve.py``).
        executor: Schedules the off-thread run. Defaults to a single-worker
            :class:`~concurrent.futures.ThreadPoolExecutor`; tests inject an inline
            executor so a job completes before :meth:`submit` returns.
    """

    def __init__(
        self, pipeline: PipelineLike, *, executor: ExecutorLike | None = None
    ) -> None:
        self._pipeline = pipeline
        self._executor: ExecutorLike = executor or ThreadPoolExecutor(max_workers=1)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, payload: Mapping[str, Any]) -> str:
        """Validate ``payload``, register a job, and schedule the run.

        Validation happens **before** scheduling so bad config fails fast (the caller
        maps :class:`ConfigError` to HTTP 400); the run itself happens off-thread.

        Raises:
            ConfigError: If the payload is invalid.
        """
        settings = settings_from_payload(payload)
        job = Job(id=uuid.uuid4().hex)
        with self._lock:
            self._jobs[job.id] = job
        self._executor.submit(self._run, job.id, settings)
        return job.id

    def _run(self, job_id: str, settings: Settings) -> None:
        """Execute the pipeline for ``job_id`` and record the outcome."""
        self._set(job_id, state=RUNNING)
        try:
            ctx = self._pipeline.run(settings)
        except Exception as exc:  # noqa: BLE001 — surface any failure to the client
            self._set(job_id, state=FAILED, error=str(exc))
            return
        artifacts = getattr(ctx, "artifacts", {}) or {}
        outputs = {fmt: str(path) for fmt, path in artifacts.get("export_paths", {}).items()}
        self._set(
            job_id,
            state=SUCCEEDED,
            outputs=outputs,
            sha256=artifacts.get("svg_sha256"),
        )

    def _set(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)

    def status(self, job_id: str) -> Job:
        """Return the job record, or raise ``KeyError`` for an unknown id."""
        with self._lock:
            return self._jobs[job_id]

    @staticmethod
    def to_dict(job: Job) -> dict[str, Any]:
        """A JSON-serializable status envelope for the HTTP layer."""
        return {
            "id": job.id,
            "state": job.state,
            "error": job.error,
            "outputs": dict(job.outputs),
            "sha256": job.sha256,
        }
