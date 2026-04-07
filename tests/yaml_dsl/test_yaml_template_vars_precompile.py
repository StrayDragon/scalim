import pytest

from scalim.dsl.by_yaml import RunOptions, compile, run_workflow
from scalim.dsl.by_yaml._internal.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.by_yaml._internal.config_parsing.template_precompile import maybe_precompile_yaml_text
from scalim.dsl.by_yaml.workflow import ScalimWorkflowConfigError, load_workflow_config


def test_template_vars_precompile_supports_unquoted_placeholders_in_demand_yaml(tmp_path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv:
      kind: csv_file
      path: {{ output_path }}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields:
      - order_id
""".lstrip(),
        encoding="utf-8",
    )

    compilation = compile(
        str(yaml_path),
        options=RunOptions(
            allowed_modules=frozenset(["tests.fixtures"]),
            template_vars={"output_path": "./output/report.xlsx"},
        ),
    )
    assert compilation.config.resources.files["detail_csv"].path == "./output/report.xlsx"


def test_template_vars_opt_in_does_not_render_when_not_provided(tmp_path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv:
      kind: csv_file
      path: "{{ output_path }}"
outputs:
  - name: detail
    to: {file: detail_csv}
    fields:
      - order_id
""".lstrip(),
        encoding="utf-8",
    )

    compilation = compile(str(yaml_path), options=RunOptions(allowed_modules=frozenset(["tests.fixtures"])))
    assert compilation.config.resources.files["detail_csv"].path == "{{ output_path }}"


def test_template_vars_precompile_applies_to_import_fragments(tmp_path) -> None:
    frag = tmp_path / "common.yaml"
    frag.write_text(
        """
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    lookup_chunk_size: {{ chunk_size }}
""".lstrip(),
        encoding="utf-8",
    )
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
name: demo
imports:
  common: ./common.yaml
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {}
sources:
  $import: common.sources
""".lstrip(),
        encoding="utf-8",
    )

    compilation = compile(
        str(demand),
        options=RunOptions(
            allowed_modules=frozenset(["tests.fixtures"]),
            template_vars={"chunk_size": 10},
        ),
    )
    assert compilation.config.sources["customers"].lookup_chunk_size == 10


def test_template_vars_missing_var_in_demand_fails_fast_with_file_context(tmp_path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv:
      kind: csv_file
      path: {{ missing }}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields:
      - order_id
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        _ = compile(
            str(yaml_path),
            options=RunOptions(
                allowed_modules=frozenset(["tests.fixtures"]),
                template_vars={},
            ),
        )
    assert "missing" in str(exc_info.value)
    assert "demand.yaml" in str(exc_info.value)


def test_template_vars_missing_var_in_import_fragment_includes_import_trace(tmp_path) -> None:
    frag = tmp_path / "common.yaml"
    frag.write_text(
        """
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    lookup_chunk_size: {{ missing }}
""".lstrip(),
        encoding="utf-8",
    )
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
name: demo
imports:
  common: ./common.yaml
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {}
sources:
  $import: common.sources
    """.lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ScalimYamlValidationError) as exc_info:
        _ = compile(
            str(demand),
            options=RunOptions(
                allowed_modules=frozenset(["tests.fixtures"]),
                template_vars={},
            ),
        )
    msg = "\n".join(env.message for env in exc_info.value.errors)
    assert "missing" in msg
    assert "import trace" in msg
    assert "common.yaml" in msg


def test_template_vars_precompile_applies_to_workflow_yaml_max_concurrency(tmp_path) -> None:
    out_path = tmp_path / "out.csv"
    demand = tmp_path / "demand.yaml"
    demand_text = (
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv:
      kind: csv_file
      path: "__OUT_PATH__"
outputs:
  - name: detail
    to: {file: detail_csv}
    fields:
      - order_id
"""
    ).lstrip()
    demand.write_text(
        demand_text.replace("__OUT_PATH__", str(out_path)),
        encoding="utf-8",
    )

    wf = tmp_path / "workflow.yaml"
    wf.write_text(
        """
workflow:
  runs:
    - id: a
      demand: demand.yaml
  options:
    max_concurrency: {{ max_concurrency }}
    failure_policy: all_fail
""".lstrip(),
        encoding="utf-8",
    )

    cfg = load_workflow_config(str(wf), template_vars={"max_concurrency": 3})
    assert cfg.options.max_concurrency == 3

    result = run_workflow(
        str(wf),
        options=RunOptions(
            allowed_modules=frozenset(["tests.fixtures"]),
            template_vars={"max_concurrency": 3},
        ),
    )
    assert result.errors() == []


def test_template_vars_missing_var_in_workflow_yaml_is_wrapped_as_workflow_config_error(tmp_path) -> None:
    wf = tmp_path / "workflow.yaml"
    wf.write_text(
        """
workflow:
  runs:
    - id: a
      demand: demand.yaml
  options:
    max_concurrency: {{ missing }}
    failure_policy: all_fail
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = load_workflow_config(str(wf), template_vars={})
    assert "missing" in str(exc_info.value)


def test_template_sandbox_safe_rejects_method_calls() -> None:
    from pathlib import Path

    yaml_text = "x: {{ p.open().read() }}\n"
    with pytest.raises(ValueError, match=r"禁止无参方法调用"):
        _ = maybe_precompile_yaml_text(
            yaml_text,
            template_vars={"p": Path("/etc/hosts")},
            context_label="repro",
            context_kind="demand",
        )


@pytest.mark.parametrize("template_sandbox", ["safe", "legacy"], ids=["safe", "legacy"])
def test_template_sandbox_rejects_underscore_attributes_in_both_modes(template_sandbox: str) -> None:
    yaml_text = "x: {{ obj.__class__ }}\n"
    with pytest.raises(ValueError, match=r"禁止访问以下划线开头属性"):
        _ = maybe_precompile_yaml_text(
            yaml_text,
            template_vars={"obj": "x"},
            context_label="repro",
            context_kind="demand",
            template_sandbox=template_sandbox,
        )


def test_template_sandbox_rejects_unknown_value() -> None:
    yaml_text = "x: {{ a }}\n"
    with pytest.raises(ValueError, match=r"`template_sandbox` 必须是以下值之一"):
        _ = maybe_precompile_yaml_text(
            yaml_text,
            template_vars={"a": 1},
            context_label="repro",
            context_kind="demand",
            template_sandbox="nope",
        )


def test_template_sandbox_common_substitutions_still_work() -> None:
    yaml_text = "\n".join(
        [
            "a: {{ a }}",
            "b: {{ m.key }}",
            "c: {{ items[0] }}",
            "",
        ]
    )
    rendered = maybe_precompile_yaml_text(
        yaml_text,
        template_vars={"a": 1, "m": {"key": "v"}, "items": ["x"]},
        context_label="repro",
        context_kind="demand",
    )
    assert "a: 1" in rendered
    assert "b: v" in rendered
    assert "c: x" in rendered


def test_template_sandbox_legacy_allows_method_calls_and_warns(caplog) -> None:
    caplog.set_level("WARNING", logger="scalim.dsl.by_yaml.template_vars")
    yaml_text = "x: {{ s.strip() }}\n"

    rendered = maybe_precompile_yaml_text(
        yaml_text,
        template_vars={"s": "  hi  "},
        context_label="repro",
        context_kind="demand",
        template_sandbox="legacy",
    )
    assert "x: hi" in rendered
    assert any("template_sandbox=legacy" in record.getMessage() for record in caplog.records)


def test_template_sandbox_safe_whitespace_is_normalized_by_public_compile_api(tmp_path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs: []
""".lstrip(),
        encoding="utf-8",
    )

    compilation = compile(
        str(yaml_path),
        options=RunOptions(
            allowed_modules=frozenset(["tests.fixtures"]),
            template_sandbox=" safe ",
        ),
    )
    assert compilation.config.name == "demo"


def test_template_sandbox_legacy_is_rejected_by_public_compile_api(tmp_path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv:
      kind: csv_file
      path: {{ output_path.strip() }}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields:
      - order_id
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        _ = compile(
            str(yaml_path),
            options=RunOptions(
                allowed_modules=frozenset(["tests.fixtures"]),
                template_vars={"output_path": "  ./out.csv  "},
                template_sandbox="legacy",
            ),
        )
    msg = str(exc_info.value)
    assert "仅允许" in msg and "safe" in msg
    assert "迁移" in msg
    assert "unsafe" in msg


def test_template_sandbox_legacy_is_available_via_unsafe_compile_entrypoint(tmp_path, caplog) -> None:
    from scalim.dsl.by_yaml.runtime.unsafe_entrypoints import unsafe_compile

    caplog.set_level("WARNING", logger="scalim.dsl.by_yaml.template_vars")
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv:
      kind: csv_file
      path: {{ output_path.strip() }}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields:
      - order_id
""".lstrip(),
        encoding="utf-8",
    )

    compilation = unsafe_compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures"]),
        template_vars={"output_path": "  ./out.csv  "},
        template_sandbox="legacy",
    )
    assert compilation.config.resources.files["detail_csv"].path == "./out.csv"
    assert any("template_sandbox=legacy" in record.getMessage() for record in caplog.records)


def test_template_sandbox_invalid_value_is_rejected_by_unsafe_entrypoints(tmp_path) -> None:
    from scalim.dsl.by_yaml.runtime.unsafe_entrypoints import unsafe_compile

    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs: []
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="template_sandbox"):
        _ = unsafe_compile(
            str(yaml_path),
            allowed_modules=frozenset(["tests.fixtures"]),
            template_sandbox="nope",
        )


def test_template_sandbox_legacy_is_available_via_unsafe_run_entrypoint(tmp_path, caplog) -> None:
    from scalim.dsl.by_yaml.runtime.unsafe_entrypoints import unsafe_run

    caplog.set_level("WARNING", logger="scalim.dsl.by_yaml.template_vars")
    yaml_path = tmp_path / "demand.yaml"
    out = tmp_path / "out.csv"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv:
      kind: csv_file
      path: {{ output_path.strip() }}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields:
      - order_id
""".lstrip(),
        encoding="utf-8",
    )

    result = unsafe_run(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures"]),
        template_vars={"output_path": "  {}  ".format(str(out))},
        template_sandbox="legacy",
    )
    assert result is not None
    assert out.exists()
    assert any("template_sandbox=legacy" in record.getMessage() for record in caplog.records)


def test_template_vars_rejects_non_json_like_types_and_does_not_leak_value() -> None:
    from pathlib import Path

    yaml_text = "x: {{ p }}\n"
    with pytest.raises(ValueError) as exc_info:
        _ = maybe_precompile_yaml_text(
            yaml_text,
            template_vars={"p": Path("/etc/hosts")},
            context_label="repro",
            context_kind="demand",
        )
    assert "路径=`template_vars['p']`" in str(exc_info.value)
    assert "/etc/hosts" not in str(exc_info.value)


def test_template_vars_rejects_dict_key_not_str() -> None:
    yaml_text = "x: {{ m }}\n"
    with pytest.raises(ValueError) as exc_info:
        _ = maybe_precompile_yaml_text(
            yaml_text,
            template_vars={"m": {1: "x"}},  # type: ignore[dict-item]
            context_label="repro",
            context_kind="demand",
        )
    assert "路径=`template_vars['m']`" in str(exc_info.value)
    assert "键类型=int" in str(exc_info.value)


def test_template_vars_rejects_top_level_key_not_str_even_without_template_markers() -> None:
    yaml_text = "x: 1\n"
    with pytest.raises(ValueError) as exc_info:
        _ = maybe_precompile_yaml_text(
            yaml_text,
            template_vars={1: "x"},  # type: ignore[dict-item]
            context_label="repro",
            context_kind="demand",
        )
    assert "路径=`template_vars`" in str(exc_info.value)
    assert "键类型=int" in str(exc_info.value)


def test_template_vars_rendered_yaml_max_len_rejects_oversized_demand_yaml(tmp_path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
outputs: []
pad: "{{ big }}"
""".lstrip(),
        encoding="utf-8",
    )

    big = "x" * 200
    with pytest.raises(ValueError) as exc_info:
        _ = compile(
            str(yaml_path),
            options=RunOptions(
                allowed_modules=frozenset(["tests.fixtures"]),
                template_vars={"big": big},
                rendered_yaml_max_len=50,
            ),
        )
    msg = str(exc_info.value)
    assert "kind=demand" in msg
    assert "rendered_len" in msg and "max_len" in msg
    assert "demand.yaml" in msg
    assert big not in msg


def test_template_vars_rendered_yaml_max_len_rejects_oversized_workflow_yaml(tmp_path) -> None:
    wf = tmp_path / "workflow.yaml"
    wf.write_text(
        """
workflow:
  runs: []
  options:
    max_concurrency: 1
    failure_policy: all_fail
  pad: "{{ big }}"
""".lstrip(),
        encoding="utf-8",
    )

    big = "x" * 200
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = load_workflow_config(
            str(wf),
            template_vars={"big": big},
            rendered_yaml_max_len=50,
        )
    msg = str(exc_info.value)
    assert "kind=workflow" in msg
    assert "rendered_len" in msg and "max_len" in msg
    assert "workflow.yaml" in msg
    assert big not in msg


def test_template_vars_rendered_yaml_max_len_rejects_oversized_import_fragment_and_includes_trace(tmp_path) -> None:
    frag = tmp_path / "common.yaml"
    frag.write_text(
        """
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    lookup_chunk_size: 10
pad: "{{ big }}"
""".lstrip(),
        encoding="utf-8",
    )
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
name: demo
imports:
  common: ./common.yaml
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {}
sources:
  $import: common.sources
outputs: []
""".lstrip(),
        encoding="utf-8",
    )

    big = "x" * 300
    with pytest.raises(ScalimYamlValidationError) as exc_info:
        _ = compile(
            str(demand),
            options=RunOptions(
                allowed_modules=frozenset(["tests.fixtures"]),
                template_vars={"big": big},
                rendered_yaml_max_len=250,
            ),
        )
    msg = "\n".join(env.message for env in exc_info.value.errors)
    assert "kind=fragment" in msg
    assert "rendered_len" in msg and "max_len" in msg
    assert "import trace" in msg
    assert "common.yaml" in msg
    assert big not in msg


def test_template_vars_rendered_yaml_max_len_rejects_non_int() -> None:
    yaml_text = "x: 1\n"
    with pytest.raises(TypeError, match=r"`rendered_yaml_max_len`"):
        _ = maybe_precompile_yaml_text(
            yaml_text,
            template_vars={"a": 1},
            context_label="repro",
            context_kind="demand",
            rendered_yaml_max_len="nope",  # type: ignore[arg-type]
        )


def test_template_vars_rendered_yaml_max_len_rejects_value_lt_1() -> None:
    yaml_text = "x: 1\n"
    with pytest.raises(ValueError, match=r"`rendered_yaml_max_len`"):
        _ = maybe_precompile_yaml_text(
            yaml_text,
            template_vars={"a": 1},
            context_label="repro",
            context_kind="demand",
            rendered_yaml_max_len=0,
        )
