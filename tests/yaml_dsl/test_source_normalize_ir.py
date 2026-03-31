import pytest

from scalim.spec.ir import SourceNormalizeIr


def test_source_normalize_index_by_key_success() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    result = normalize.apply([{"id": 1, "v": "a"}, {"id": 2, "v": "b"}], source_id="s1")
    assert result[1]["v"] == "a"
    assert result[2]["v"] == "b"


def test_source_normalize_index_by_key_duplicate_error() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    with pytest.raises(ValueError, match="duplicate key"):
        _ = normalize.apply([{"id": 1, "v": "a"}, {"id": 1, "v": "b"}], source_id="s1")


def test_source_normalize_index_by_key_duplicate_first() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id", on_conflict="first")
    result = normalize.apply([{"id": 1, "v": "a"}, {"id": 1, "v": "b"}], source_id="s1")
    assert result[1]["v"] == "a"


def test_source_normalize_index_by_key_duplicate_last() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id", on_conflict="last")
    result = normalize.apply([{"id": 1, "v": "a"}, {"id": 1, "v": "b"}], source_id="s1")
    assert result[1]["v"] == "b"


def test_source_normalize_unknown_kind_rejected() -> None:
    normalize = SourceNormalizeIr(kind="unknown", key_field="id")
    with pytest.raises(ValueError, match="Unknown normalize\\.kind"):
        _ = normalize.apply([], source_id="s1")


def test_source_normalize_index_by_key_accepts_mapping_passthrough() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    mapping = {1: {"id": 1, "v": "a"}}
    assert normalize.apply(mapping, source_id="s1") is mapping


def test_source_normalize_index_by_key_rejects_non_list_result() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    with pytest.raises(TypeError, match="expected loader result list\\[row\\]"):
        _ = normalize.apply("not-a-list", source_id="s1")


def test_source_normalize_index_by_key_rejects_non_mapping_row() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    with pytest.raises(TypeError, match="row is a Mapping"):
        _ = normalize.apply([1], source_id="s1")


def test_source_normalize_index_by_key_rejects_missing_key_field_in_row() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    with pytest.raises(KeyError, match="missing key_field"):
        _ = normalize.apply([{"other": 1}], source_id="s1")


def test_source_normalize_index_by_key_rejects_none_key_value() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    with pytest.raises(ValueError, match="is None"):
        _ = normalize.apply([{"id": None}], source_id="s1")


def test_source_normalize_index_by_key_rejects_invalid_on_conflict() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id", on_conflict="bad")
    with pytest.raises(ValueError, match="invalid on_conflict"):
        _ = normalize.apply([{"id": 1, "v": "a"}, {"id": 1, "v": "b"}], source_id="s1")


def test_source_normalize_index_by_key_rejects_unhashable_key_value() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    with pytest.raises(TypeError, match="must be hashable"):
        _ = normalize.apply([{"id": []}], source_id="s1")


def test_source_normalize_take_first_on_empty_miss_removes_key() -> None:
    normalize = SourceNormalizeIr(kind="take_first", on_empty="miss")
    result = normalize.apply({1: [], 2: [{"v": "ok"}]}, source_id="s1")
    assert 1 not in result
    assert result[2]["v"] == "ok"


def test_source_normalize_take_first_on_empty_null_sets_none() -> None:
    normalize = SourceNormalizeIr(kind="take_first", on_empty="null")
    result = normalize.apply({1: []}, source_id="s1")
    assert result[1] is None


def test_source_normalize_take_first_on_empty_error_raises() -> None:
    normalize = SourceNormalizeIr(kind="take_first", on_empty="error")
    with pytest.raises(ValueError, match="empty candidates list"):
        _ = normalize.apply({1: []}, source_id="s1")


def test_source_normalize_take_first_rejects_list_result() -> None:
    normalize = SourceNormalizeIr(kind="take_first", on_empty="miss")
    with pytest.raises(TypeError, match="does not support loader result list\\[row\\]"):
        _ = normalize.apply([{"id": 1}], source_id="s1")


def test_source_normalize_project_fields_supports_int_key_extract_and_from_key() -> None:
    from scalim.dsl.by_yaml._internal.config_parsing.field_extract import compile_field_extract
    from scalim.spec.ir import SourceNormalizeProjectFieldRuleIr

    fields = (
        SourceNormalizeProjectFieldRuleIr(name="order_id", from_key=True),
        SourceNormalizeProjectFieldRuleIr(
            name="customer_level",
            extract_expr="[1].clearn_reason_level",
            extract_segments=compile_field_extract("[1].clearn_reason_level"),
        ),
        SourceNormalizeProjectFieldRuleIr(
            name="operation_level",
            extract_expr="[2].clearn_reason_level",
            extract_segments=compile_field_extract("[2].clearn_reason_level"),
        ),
        SourceNormalizeProjectFieldRuleIr(
            name="review_status",
            extract_expr="review_status",
            extract_segments=compile_field_extract("review_status"),
        ),
    )
    normalize = SourceNormalizeIr(kind="project_fields", fields=fields, on_missing="error")
    result = normalize.apply(
        {
            10001: {
                1: {"clearn_reason_level": 2},
                2: {"clearn_reason_level": 1},
                "review_status": 3,
            }
        },
        source_id="s1",
    )
    assert result[10001]["order_id"] == 10001
    assert result[10001]["customer_level"] == 2
    assert result[10001]["operation_level"] == 1
    assert result[10001]["review_status"] == 3


def test_source_normalize_map_values_pipeline_take_first_then_project_fields() -> None:
    from scalim.dsl.by_yaml._internal.config_parsing.field_extract import compile_field_extract
    from scalim.spec.ir import SourceNormalizeProjectFieldRuleIr, SourceNormalizeStepIr

    project_fields = (
        SourceNormalizeProjectFieldRuleIr(name="order_id", from_key=True),
        SourceNormalizeProjectFieldRuleIr(
            name="review_status",
            extract_expr="review_status",
            extract_segments=compile_field_extract("review_status"),
        ),
    )
    steps = (
        SourceNormalizeStepIr(kind="take_first", on_empty="miss"),
        SourceNormalizeStepIr(kind="project_fields", on_missing="error", fields=project_fields),
    )
    normalize = SourceNormalizeIr(kind="map_values", steps=steps)
    result = normalize.apply({10001: [{"review_status": 3}], 10002: []}, source_id="s1")
    assert 10002 not in result
    assert result[10001]["order_id"] == 10001
    assert result[10001]["review_status"] == 3


def test_source_normalize_call_by_requires_mapping_return() -> None:
    def bad_return(result: object) -> object:
        return []

    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id", call_by=bad_return)
    with pytest.raises(TypeError, match="must return Mapping.*sources\\.s1\\.normalize\\.call_by"):
        _ = normalize.apply([{"id": 1}], source_id="s1")


def test_source_normalize_call_by_accepts_ctx_keyword() -> None:
    def identity(result: object, *, ctx: object) -> object:
        _ = ctx
        return result

    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id", call_by=identity)
    result = normalize.apply([{"id": 1, "v": "x"}], source_id="s1")
    assert result[1]["v"] == "x"


def test_source_normalize_step_apply_value_rejects_unknown_kind() -> None:
    from scalim.spec.ir import SourceNormalizeStepIr

    step = SourceNormalizeStepIr(kind="bad")
    with pytest.raises(ValueError, match="Unknown normalize\\.step\\.kind"):
        _ = step.apply_value({}, lookup_key=1, source_id="s1", step_index=0)


def test_normalize_call_by_rejects_non_mapping_input() -> None:
    from scalim.spec.ir._sources import _normalize_call_by

    def identity(result: object) -> object:
        return result

    with pytest.raises(TypeError, match="expected Mapping input"):
        _ = _normalize_call_by(123, source_id="s1", kind="index_by_key", call_by=identity)


def test_normalize_call_by_rejects_fn_without_args() -> None:
    from scalim.spec.ir._sources import _normalize_call_by

    def bad_call_by() -> object:  # type: ignore[no-untyped-def]
        return {}

    with pytest.raises(TypeError, match="failed to call function"):
        _ = _normalize_call_by({}, source_id="s1", kind="index_by_key", call_by=bad_call_by)


def test_normalize_call_by_falls_back_when_signature_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    import scalim.spec.ir._sources as sources_module

    def _raise_value_error(_: object) -> object:
        raise ValueError("no signature")

    monkeypatch.setattr(sources_module.inspect, "signature", _raise_value_error)

    def identity(result: object) -> object:
        return result

    returned = sources_module._normalize_call_by({}, source_id="s1", kind="index_by_key", call_by=identity)
    assert returned == {}


def test_normalize_call_by_fallback_supports_ctx_keyword(monkeypatch: pytest.MonkeyPatch) -> None:
    import scalim.spec.ir._sources as sources_module

    def _raise_value_error(_: object) -> object:
        raise ValueError("no signature")

    monkeypatch.setattr(sources_module.inspect, "signature", _raise_value_error)

    def identity(result: object, *, ctx: object) -> object:
        _ = ctx
        return result

    returned = sources_module._normalize_call_by({}, source_id="s1", kind="index_by_key", call_by=identity)
    assert returned == {}


def test_normalize_call_by_fallback_does_not_swallow_type_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import scalim.spec.ir._sources as sources_module

    def _raise_value_error(_: object) -> object:
        raise ValueError("no signature")

    monkeypatch.setattr(sources_module.inspect, "signature", _raise_value_error)

    def boom(result: object, ctx: object) -> object:
        _ = result
        _ = ctx
        raise TypeError("boom")

    with pytest.raises(TypeError, match="boom"):
        _ = sources_module._normalize_call_by({}, source_id="s1", kind="index_by_key", call_by=boom)


def test_normalize_call_by_fallback_does_not_swallow_type_error_from_ctx_keyword_call(monkeypatch: pytest.MonkeyPatch) -> None:
    import scalim.spec.ir._sources as sources_module

    def _raise_value_error(_: object) -> object:
        raise ValueError("no signature")

    monkeypatch.setattr(sources_module.inspect, "signature", _raise_value_error)

    def boom_kwonly_ctx(result: object, *, ctx: object) -> object:
        _ = result
        _ = ctx
        raise TypeError("boom")

    with pytest.raises(TypeError, match="boom"):
        _ = sources_module._normalize_call_by({}, source_id="s1", kind="index_by_key", call_by=boom_kwonly_ctx)


def test_normalize_call_by_works_when_positional_only_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    import scalim.spec.ir._sources as sources_module

    parameter_cls = sources_module.inspect.Parameter
    if not hasattr(parameter_cls, "POSITIONAL_ONLY"):
        pytest.skip("inspect.Parameter.POSITIONAL_ONLY not available")

    monkeypatch.delattr(parameter_cls, "POSITIONAL_ONLY")

    def identity(result: object, *, ctx: object) -> object:
        _ = ctx
        return result

    returned = sources_module._normalize_call_by({}, source_id="s1", kind="index_by_key", call_by=identity)
    assert returned == {}


def test_normalize_call_by_accepts_varargs() -> None:
    from scalim.spec.ir._sources import _normalize_call_by

    def identity(*args: object) -> object:
        return args[0]

    returned = _normalize_call_by({}, source_id="s1", kind="index_by_key", call_by=identity)
    assert returned == {}


def test_normalize_call_by_accepts_varargs_with_ctx_kwonly() -> None:
    from scalim.spec.ir._sources import _normalize_call_by

    def identity(*args: object, ctx: object) -> object:
        _ = ctx
        return args[0]

    returned = _normalize_call_by({}, source_id="s1", kind="index_by_key", call_by=identity)
    assert returned == {}


def test_source_normalize_take_first_rejects_non_mapping_result() -> None:
    normalize = SourceNormalizeIr(kind="take_first", on_empty="miss")
    with pytest.raises(TypeError, match="expected loader result mapping\\[key -> list\\[row\\]\\]"):
        _ = normalize.apply("not-a-mapping", source_id="s1")


def test_source_normalize_take_first_rejects_non_list_candidates() -> None:
    normalize = SourceNormalizeIr(kind="take_first", on_empty="miss")
    with pytest.raises(TypeError, match="expected list\\[row\\]"):
        _ = normalize.apply({1: "not-a-list"}, source_id="s1")


def test_source_normalize_take_first_rejects_invalid_on_empty() -> None:
    normalize = SourceNormalizeIr(kind="take_first", on_empty="bad")
    with pytest.raises(ValueError, match="invalid on_empty"):
        _ = normalize.apply({1: []}, source_id="s1")


def test_source_normalize_take_first_rejects_non_mapping_row() -> None:
    normalize = SourceNormalizeIr(kind="take_first", on_empty="miss")
    with pytest.raises(TypeError, match="expected row to be a Mapping"):
        _ = normalize.apply({1: [123]}, source_id="s1")


def test_source_normalize_project_fields_rejects_non_mapping_result() -> None:
    normalize = SourceNormalizeIr(kind="project_fields", fields=(), on_missing="error")
    with pytest.raises(TypeError, match="normalize\\.project_fields expected loader result mapping"):
        _ = normalize.apply("not-a-mapping", source_id="s1")


def test_source_normalize_project_fields_rejects_non_mapping_row() -> None:
    normalize = SourceNormalizeIr(kind="project_fields", fields=(), on_missing="error")
    with pytest.raises(TypeError, match="expected row to be a Mapping"):
        _ = normalize.apply({1: "not-a-row"}, source_id="s1")


def test_source_normalize_project_fields_on_missing_variants() -> None:
    from scalim.dsl.by_yaml._internal.config_parsing.field_extract import compile_field_extract
    from scalim.spec.ir import SourceNormalizeProjectFieldRuleIr

    fields = (
        SourceNormalizeProjectFieldRuleIr(
            name="missing",
            from_key=False,
            extract_expr="missing",
            extract_segments=compile_field_extract("missing"),
        ),
    )

    normalize = SourceNormalizeIr(kind="project_fields", fields=fields, on_missing="null")
    result = normalize.apply({1: {}}, source_id="s1")
    assert result[1]["missing"] is None

    normalize = SourceNormalizeIr(kind="project_fields", fields=fields, on_missing="bad")
    with pytest.raises(ValueError, match="invalid on_missing"):
        _ = normalize.apply({1: {}}, source_id="s1")

    normalize = SourceNormalizeIr(kind="project_fields", fields=fields, on_missing="error")
    with pytest.raises(KeyError, match="missing extract"):
        _ = normalize.apply({1: {}}, source_id="s1")


def test_source_normalize_map_values_rejects_non_mapping_result() -> None:
    normalize = SourceNormalizeIr(kind="map_values", steps=())
    with pytest.raises(TypeError, match="expected loader result Mapping"):
        _ = normalize.apply("not-a-mapping", source_id="s1")


def test_extract_segments_with_presence_branches() -> None:
    from scalim.spec.ir._sources import _extract_segments_with_presence

    ok, value = _extract_segments_with_presence({"x": None}, ("x", "y"))
    assert ok is False
    assert value is None

    ok, value = _extract_segments_with_presence({"x": {}}, ("x", "missing"))
    assert ok is False
    assert value is None


def test_extract_segment_with_presence_branches() -> None:
    from types import SimpleNamespace

    from scalim.spec.ir._sources import _extract_segment_with_presence

    ok, value = _extract_segment_with_presence(SimpleNamespace(x=1), "x")
    assert ok is True
    assert value == 1

    class _Indexable:
        def __getitem__(self, key: object) -> object:
            if key == "x":
                return 123
            raise KeyError(key)

    ok, value = _extract_segment_with_presence(_Indexable(), "x")
    assert ok is True
    assert value == 123

    ok, value = _extract_segment_with_presence(_Indexable(), "missing")
    assert ok is False
    assert value is None

    ok, value = _extract_segment_with_presence([1], 0)
    assert ok is False
    assert value is None
