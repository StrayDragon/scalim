from pathlib import Path


def test_in_memory_rows_has_stable_facade_import_path_and_no_internal_import_leaks() -> None:
    from scalim.sinks.rows import InMemoryRows  # noqa: PLC0415

    assert InMemoryRows.__name__ == "InMemoryRows"

    import scalim.execution.run_ir as run_ir_module  # noqa: PLC0415
    import scalim.workflow.execute as workflow_execute_module  # noqa: PLC0415

    assert "sinks._internal.rows" not in Path(str(run_ir_module.__file__)).read_text(encoding="utf-8")
    assert "sinks._internal.rows" not in Path(str(workflow_execute_module.__file__)).read_text(encoding="utf-8")
