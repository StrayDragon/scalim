import inspect
from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, compile
from scalim.dsl.yaml_dsl.params_template import CompiledParamsTemplate, LiteralNode
from scalim.dsl.yaml_dsl.runtime.errors import ScalimResolverError
from scalim.dsl.yaml_dsl.runtime._internal.callable_preflight import ScalimCallablePreflightError
from scalim.dsl.yaml_dsl.runtime._internal.callable_preflight import (
    format_signature_bind_mismatch_message,
    validate_signature_accepts_any_candidate,
    validate_signature_binds_kwargs_keys,
)
from scalim.execution.loader_retry import LoaderRetryPoliciesSpec, LoaderRetryPolicySpec


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "demand.yaml"
    path.write_text(text.lstrip(), encoding="utf-8")
    return path


def test_normalize_call_by_signature_precheck_rejects_kwonly_result(tmp_path: Path) -> None:
    yaml_text = """
name: demo
main_source:
  source_id: orders
  loader: "tests.fixtures.source_normalize_loaders:load_orders_main"
  fields:
    order_id:
      extract: order_id
sources:
  s1:
    loader: "tests.fixtures.source_normalize_loaders:load_recommends_list"
    key: order_id
    normalize:
      kind: index_by_key
      call_by: "tests.fixtures.callable_preflight_mod:norm_kwonly_result"
"""
    yaml_path = _write(tmp_path, yaml_text)
    with pytest.raises(ScalimResolverError) as excinfo:
        _ = compile(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(
                    allowed_modules=frozenset(
                        [
                            "tests.fixtures.callable_preflight_mod",
                            "tests.fixtures.source_normalize_loaders",
                        ]
                    )
                )
            ),
        )
    msg = str(excinfo.value)
    assert "sources.s1.normalize.call_by" in msg
    assert "函数签名不匹配" in msg


def test_validate_signature_binds_kwargs_keys_noops_on_empty_keys() -> None:
    def _fn(**_kwargs):  # type: ignore[no-untyped-def]
        return None

    validate_signature_binds_kwargs_keys(
        location="case",
        reference="demo.fn",
        fn=_fn,
        kwargs_keys=(),
    )


@pytest.mark.parametrize(
    "ref",
    [
        "tests.fixtures.callable_preflight_mod:norm_result_only",
        "tests.fixtures.callable_preflight_mod:norm_result_ctx_positional",
        "tests.fixtures.callable_preflight_mod:norm_result_ctx_kwonly",
    ],
    ids=["result_only", "result_ctx_pos", "result_ctx_kwonly"],
)
def test_normalize_call_by_signature_precheck_accepts_result_and_ctx_shapes(tmp_path: Path, ref: str) -> None:
    yaml_text = """
name: demo
main_source:
  source_id: orders
  loader: "tests.fixtures.source_normalize_loaders:load_orders_main"
  fields:
    order_id:
      extract: order_id
sources:
  s1:
    loader: "tests.fixtures.source_normalize_loaders:load_recommends_list"
    key: order_id
    normalize:
      kind: index_by_key
      call_by: "{ref}"
""".format(ref=ref)
    yaml_path = _write(tmp_path, yaml_text)
    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(
                allowed_modules=frozenset(
                    [
                        "tests.fixtures.callable_preflight_mod",
                        "tests.fixtures.source_normalize_loaders",
                    ]
                )
            )
        ),
    )
    assert compilation.request is not None


def test_loader_params_signature_precheck_rejects_unknown_kw(tmp_path: Path) -> None:
    yaml_text = """
name: demo
main_source:
  source_id: orders
  loader: "tests.fixtures.source_normalize_loaders:load_orders_main"
  fields:
    order_id:
      extract: order_id
sources:
  s1:
    loader: "tests.fixtures.callable_preflight_mod:load_ref_table"
    key: id
    params:
      bad_key: 1
    """
    yaml_path = _write(tmp_path, yaml_text)
    with pytest.raises(ScalimResolverError) as excinfo:
        _ = compile(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(
                    allowed_modules=frozenset(
                        [
                            "tests.fixtures.callable_preflight_mod",
                            "tests.fixtures.source_normalize_loaders",
                        ]
                    )
                )
            ),
        )
    msg = str(excinfo.value)
    assert "sources.s1.params" in msg
    assert "bad_key" in msg


def test_loader_params_signature_precheck_rejects_missing_required_kw(tmp_path: Path) -> None:
    yaml_text = """
name: demo
main_source:
  source_id: orders
  loader: "tests.fixtures.source_normalize_loaders:load_orders_main"
  fields:
    order_id:
      extract: order_id
sources:
  s1:
    loader: "tests.fixtures.callable_preflight_mod:load_ref_table"
    key: id
    params:
      field_keys: ["id"]
    """
    yaml_path = _write(tmp_path, yaml_text)
    with pytest.raises(ScalimResolverError) as excinfo:
        _ = compile(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(
                    allowed_modules=frozenset(
                        [
                            "tests.fixtures.callable_preflight_mod",
                            "tests.fixtures.source_normalize_loaders",
                        ]
                    )
                )
            ),
        )
    msg = str(excinfo.value)
    assert "sources.s1.params" in msg
    assert "missing" in msg or "required" in msg


def test_main_source_params_signature_precheck_rejects_missing_required_kw(tmp_path: Path) -> None:
    yaml_text = """
name: demo
main_source:
  source_id: orders
  loader: "tests.fixtures.callable_preflight_mod:load_main_rows_with_optional"
  params:
    tag: "demo"
  fields:
    order_id:
      extract: order_id
    """
    yaml_path = _write(tmp_path, yaml_text)
    with pytest.raises(ScalimResolverError) as excinfo:
        _ = compile(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.callable_preflight_mod"]))
            ),
        )
    msg = str(excinfo.value)
    assert "main_source.params" in msg
    assert "missing" in msg or "required" in msg


def test_should_retry_signature_precheck_rejects_kwonly(tmp_path: Path) -> None:
    yaml_text = """
name: demo
main_source:
  source_id: orders
  loader: "tests.fixtures.source_normalize_loaders:load_orders_main"
  fields:
    order_id:
      extract: order_id
"""
    yaml_path = _write(tmp_path, yaml_text)

    def bad_should_retry(*, exc: Exception, ctx: object) -> bool:  # type: ignore[no-untyped-def]
        _ = (exc, ctx)
        return True

    with pytest.raises(ScalimCallablePreflightError) as excinfo:
        _ = compile(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.source_normalize_loaders"])),
                runtime=DemandRunRuntimeOptions(
                    loader_retry=LoaderRetryPoliciesSpec(
                        default=LoaderRetryPolicySpec(enabled=True, should_retry=bad_should_retry, max_attempts=2)
                    )
                ),
            ),
        )
    msg = str(excinfo.value)
    assert "loader_retry.default.should_retry" in msg
    assert "函数签名不匹配" in msg


def test_params_template_top_level_mapping_string_keys_returns_empty_for_non_mapping() -> None:
    template = CompiledParamsTemplate(root=LiteralNode(value=1))
    assert template.top_level_mapping_string_keys() == ()


def test_validate_signature_accepts_any_candidate_rejects_empty_candidates() -> None:
    def _fn(a: object) -> object:
        return a

    with pytest.raises(ScalimCallablePreflightError, match="candidates missing"):
        validate_signature_accepts_any_candidate(
            location="case-empty-candidates",
            reference="ref",
            fn=_fn,
            candidates=(),
        )


def test_format_signature_bind_mismatch_message_supports_empty_candidates_display() -> None:
    def _fn(a: object) -> object:
        return a

    msg = format_signature_bind_mismatch_message(
        location="case-empty-display",
        reference="ref",
        signature=inspect.signature(_fn),
        bind_error=TypeError("boom"),
        candidates=(),
    )
    assert "call=``" in msg


def test_should_retry_signature_precheck_falls_back_to_repr_when_callable_has_no___name__(tmp_path: Path) -> None:
    yaml_text = """
name: demo
main_source:
  source_id: orders
  loader: "tests.fixtures.source_normalize_loaders:load_orders_main"
  fields:
    order_id:
      extract: order_id
"""
    yaml_path = _write(tmp_path, yaml_text)

    class _NoNameCallable:
        def __call__(self, exc: Exception, ctx: object) -> bool:  # type: ignore[no-untyped-def]
            _ = (exc, ctx)
            return True

    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.source_normalize_loaders"])),
            runtime=DemandRunRuntimeOptions(
                loader_retry=LoaderRetryPoliciesSpec(
                    default=LoaderRetryPolicySpec(enabled=True, should_retry=_NoNameCallable(), max_attempts=2)
                )
            ),
        ),
    )
    assert compilation.request is not None
