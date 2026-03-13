import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict

from scalim.dsl.by_yaml import run
from scalim.execution.loader_retry import LoaderRetryPoliciesSpec, LoaderRetryPolicySpec
from scalim.sinks.sink_memory import InMemoryRowSink

from ..by_yaml_dsl import loader_retry_demo_mod as demo_mod
from ._types import ChapterResult


def run_loader_retry() -> ChapterResult:
    """YAML DSL 加载重试: 不启用则失败 / 启用后自动重试成功."""
    yaml_no_retry = textwrap.dedent(
        """
        name: loader_retry_demo

        main_source:
          source_id: orders
          loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.loader_retry_demo_mod:load_orders"
          fields:
            order_id:
              {}
        """
    ).lstrip()

    yaml_with_retry = textwrap.dedent(
        """
        name: loader_retry_demo

        _templates:
          retry:
            transient_default: &transient_default
              enabled: true
              max_attempts: 5
              max_elapsed_seconds: 5.0
              backoff: fixed
              base_delay_seconds: 0.0
              max_delay_seconds: 0.0
              jitter: false

        retry:
          <<: *transient_default
          max_attempts: 2

        main_source:
          source_id: orders
          loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.loader_retry_demo_mod:load_orders"
          fields:
            order_id:
              {}
        """
    ).lstrip()

    allowed_modules = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.loader_retry_demo_mod"])

    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_no_retry_path = Path(tmpdir) / "no_retry.yaml"
        yaml_with_retry_path = Path(tmpdir) / "with_retry.yaml"
        yaml_no_retry_path.write_text(yaml_no_retry, encoding="utf-8")
        yaml_with_retry_path.write_text(yaml_with_retry, encoding="utf-8")

        # 1) 不启用 `retry`: 第一次失败直接抛错
        demo_mod.reset()
        sink_no_retry = InMemoryRowSink()
        no_retry_ok = False
        try:
            _ = run(str(yaml_no_retry_path), allowed_modules=allowed_modules, sink=sink_no_retry)
        except demo_mod.TransientError:
            no_retry_ok = True

        # 2) 启用 `retry`: 自动重试后成功
        demo_mod.reset()
        sink_with_retry = InMemoryRowSink()
        injected_retry = LoaderRetryPoliciesSpec(default=LoaderRetryPolicySpec(should_retry=demo_mod.should_retry))
        _ = run(
            str(yaml_with_retry_path),
            allowed_modules=allowed_modules,
            sink=sink_with_retry,
            loader_retry=injected_retry,
        )
        expected_call_count = 2
        with_retry_ok = sink_with_retry.get_data() == [{"order_id": 1}] and demo_mod.get_call_count() == expected_call_count

    passed = bool(no_retry_ok and with_retry_ok)
    summary = "no_retry_ok={} with_retry_ok={}".format(no_retry_ok, with_retry_ok)
    details: Dict[str, Any] = {"call_count": demo_mod.get_call_count()}
    return ChapterResult(chapter_id="loader_retry", passed=passed, summary=summary, details=details)
