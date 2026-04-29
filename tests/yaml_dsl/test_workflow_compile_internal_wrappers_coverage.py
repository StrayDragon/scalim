from pathlib import Path


def test_workflow_compile_internal_wrappers_are_exercised(tmp_path: Path) -> None:
    from scalim.dsl.yaml_dsl import workflow_compile as workflow_compile_mod
    from scalim.dsl.yaml_dsl.schema_dsl.models import BookWriteDefaultsConfig
    from scalim.dsl.yaml_dsl.workflow_types import (
        WorkflowOutputStagingOptions,
        WorkflowResourcesWaitDiagnosticsOptions,
        WorkflowResourcesWaitOptions,
    )

    out = workflow_compile_mod._as_abs_path(str(tmp_path / "x"))  # noqa: SLF001
    assert isinstance(out, str)
    assert str(tmp_path) in out

    base = workflow_compile_mod._demand_base_dir(str(tmp_path / "a" / "b.yaml"))  # noqa: SLF001
    assert base == (tmp_path / "a")

    ref = workflow_compile_mod._outputs_path_ref("outputs", 1, "to.book")  # noqa: SLF001
    assert ref == "outputs.1.to.book"

    defaults = BookWriteDefaultsConfig(mode="sheet", on_conflict="error")
    node = workflow_compile_mod._build_write_node_for_book(  # noqa: SLF001
        node_id="n1",
        decl_order=0,
        deps=(),
        book_id="b1",
        sheet_name="s1",
        input_node_id="in",
        input_output_id="out",
        mode="sheet",
        write_defaults=defaults,
        write_defaults_mode_path="p",
    )
    assert str(node.node_id) == "n1"

    resources_wait = WorkflowResourcesWaitOptions(
        max_wait_s=1.0,
        diagnostics=WorkflowResourcesWaitDiagnosticsOptions(
            enabled=True,
            warn_after_s=0.1,
            repeat_every_s=None,
            capture_owner_callsite=False,
        ),
    )
    wait_ir = workflow_compile_mod._build_workflow_resources_wait_ir(resources_wait)  # noqa: SLF001
    assert wait_ir.max_wait_s == 1.0

    staging = WorkflowOutputStagingOptions(dir_name="staging", keep_on_success=True, keep_on_failure=False)
    staging_ir = workflow_compile_mod._build_workflow_output_staging_ir(staging)  # noqa: SLF001
    assert staging_ir.dir_name == "staging"
