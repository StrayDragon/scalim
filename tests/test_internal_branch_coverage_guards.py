import os
from typing import Any, List, Tuple

import pytest

import concurrent.futures

from scalim.execution.adaptive._internal.loadref_scheduler_support import run_task_in_process
from scalim.execution.adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
from scalim.execution.adaptive.policy import (
    ADAPTIVE_BACKEND_PROCESS,
    ADAPTIVE_BACKEND_THREAD,
    PROCESS_FAILURE_FAIL_FAST,
    PROCESS_FAILURE_FALLBACK_SERIAL,
    AdaptivePolicy,
)
from scalim.execution.adaptive.strategy_unit import TaskSpec
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.pipeline.overrides import PipelineOverrides
from scalim.hooks.base import HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.plan import ExecutionPlan
from scalim.execution.context import BatchContext
from scalim.dsl.by_yaml.config_parsing.models import FieldDef
from scalim.dsl.by_yaml.config_parsing.validators._internal.validator_fields_output import ValidatorFieldOutputMixin
from scalim.dsl.by_yaml.schema_dsl.constants import FIELD_KIND_DERIVED
from scalim.ob.presets._internal import viz_handlers as viz_handlers_module
from scalim.ob.presets._internal import viz_output as viz_output_module


class _BrokenLen:
    def __len__(self) -> int:
        raise TypeError("no len")


class _OutputValidator(ValidatorFieldOutputMixin):
    def _add_error(self, errors: List[Tuple[str, str]], message: str, *, path: str) -> None:
        errors.append((message, path))


def test_validator_output_source_ambiguity_skips_non_source_field() -> None:
    validator = _OutputValidator()
    errors: List[Tuple[str, str]] = []

    validator._validate_output_field_source_ambiguity(
        FieldDef(field_id="derived_only", kind=FIELD_KIND_DERIVED, data={}, source_id=None),
        "string",
        {"": {"derived_only"}},
        errors,
    )

    assert errors == []


def test_internal_viz_handler_helpers_cover_guard_branches() -> None:
    assert viz_handlers_module._safe_len(_BrokenLen()) == 0
    assert viz_handlers_module._sample_value([1, 2, 3], 0) is None
    assert viz_handlers_module._sample_value(None, 2) is None

    sampled = viz_handlers_module._sample_value(set([1, 2, 3]), 1)
    assert isinstance(sampled, list)
    assert len(sampled) == 1

    marker = object()
    assert viz_handlers_module._sample_value(marker, 1) is marker


def test_internal_viz_output_default_dir_covers_platform_branches(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(viz_output_module.platform, "system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    assert viz_output_module._default_viz_dir().endswith(os.path.join("appdata", "scalim-viz"))

    monkeypatch.setattr(viz_output_module.platform, "system", lambda: "Darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert "Application Support" in viz_output_module._default_viz_dir()


class _RecordingPool:
    def __init__(self) -> None:
        self.calls = []

    def submit(self, fn, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        self.calls.append((fn, args, kwargs))
        fut = concurrent.futures.Future()
        fut.set_result("submitted")
        return fut


class _InvalidProcessFailurePolicy(AdaptivePolicy):
    def choose_process_failure_mode(self, *, plan, runtime, tuning):  # type: ignore[override]
        _ = plan
        _ = runtime
        _ = tuning
        return "invalid"


def test_adaptive_execution_internal_helpers_cover_process_paths() -> None:
    plan = ExecutionPlan()
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=PipelineOverrides(adaptive_policy=_InvalidProcessFailurePolicy()))
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=None)
    runtime.adaptive_process_failure_mode = PROCESS_FAILURE_FALLBACK_SERIAL

    assert scheduler._process_failure_mode(runtime) == PROCESS_FAILURE_FALLBACK_SERIAL  # noqa: SLF001
    runtime.adaptive_process_failure_mode = None
    assert scheduler._process_failure_mode(runtime) == PROCESS_FAILURE_FAIL_FAST  # noqa: SLF001
    assert scheduler._should_use_process_backend(ADAPTIVE_BACKEND_PROCESS) is True  # noqa: SLF001
    assert scheduler._should_use_process_backend(ADAPTIVE_BACKEND_THREAD) is False  # noqa: SLF001

    pool = _RecordingPool()
    context = BatchContext()
    spec = TaskSpec(op=object(), relation_key=(("k",),), group_enabled=True, pool_name="default")
    future = scheduler._submit_process_task(  # noqa: SLF001
        spec,
        pool=pool,
        context=context,
        batch_row_nth=[0],
        runtime=runtime,
        required_fields=None,
    )

    assert future.result() == "submitted"
    assert len(pool.calls) == 1
    fn, args, kwargs = pool.calls[0]
    assert fn is run_task_in_process
    assert args[0] is plan
    assert args[3] is not context
    assert args[4] == [0]
    assert kwargs == {"group_enabled": True}
