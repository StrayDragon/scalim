from pathlib import Path

from scalim.dsl.yaml_dsl.runtime.compiler import compile as compile_demand
from scalim.dsl.yaml_dsl.runtime.contracts import DemandRunOptions, DemandRunOutputOptions, DemandRunSecurityOptions
from scalim.execution.run_ir import run_ir


_ALLOWED_MODULES = frozenset(["tests.fixtures.workflow_loaders"])


def test_workflow_managed_pathless_csv_returns_in_memory_output(tmp_path: Path) -> None:
    yaml_path = tmp_path / "a.yaml"
    yaml_path.write_text(
        (
            """
name: a
main_source:
  source_id: main
  loader: "tests.fixtures.workflow_loaders:load_table_a_fast"
  fields:
    id: {extract: id}
    value: {extract: value}
resources:
  books:
    report:
      kind: xlsx_memory
      budget: {max_sheets: 10, max_total_cells: 1000}
outputs:
  - name: detail
    to:
      book: report
    fields: [id, value]
"""
        ).lstrip(),
        encoding="utf-8",
    )

    opts = DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
        outputs=DemandRunOutputOptions(workflow_managed_output_ids=frozenset(["detail"])),
    )
    compilation = compile_demand(str(yaml_path), options=opts)
    result = run_ir(compilation.demand_ir, compilation.request)

    assert result.outputs == {}
    assert result.in_memory_rows_outputs is not None
    assert result.in_memory_rows_outputs["detail"].header == ["id", "value"]
    assert result.in_memory_rows_outputs["detail"].rows[-1] == ["a2", "A2"]
    assert result.in_memory_csv_outputs is not None
    assert result.in_memory_csv_outputs["detail"].header == ["id", "value"]
    assert result.in_memory_csv_outputs["detail"].rows[-1] == ["a2", "A2"]
