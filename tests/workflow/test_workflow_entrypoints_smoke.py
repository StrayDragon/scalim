import json
import threading
from pathlib import Path

from scalim.dsl.by_yaml import run_workflow as run_workflow_public
from scalim.dsl.by_yaml.workflow_entrypoints import run_workflow as run_workflow_stable


def _write_demand_yaml(tmp_path: Path, *, file_name: str, name: str, output_path: Path) -> Path:
    yaml_content = """
name: {name}
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {{}}
outputs:
  - name: detail
    container: {{type: csv, path: {output_path}}}
    fields: [order_id]
""".format(
        name=str(name),
        output_path=json.dumps(str(output_path)),
    )

    p = tmp_path / str(file_name)
    p.write_text(yaml_content, encoding="utf-8")
    return p


def _write_workflow_yaml(tmp_path: Path, *, file_name: str, run_id: str, demand_file: str) -> Path:
    yaml_content = """
workflow:
  runs:
    - id: {run_id}
      demand: {demand_file}
  options:
    max_concurrency: 1
    failure_policy: all_fail
""".format(
        run_id=str(run_id),
        demand_file=str(demand_file),
    )

    p = tmp_path / str(file_name)
    p.write_text(yaml_content, encoding="utf-8")
    return p


def test_stable_workflow_entrypoints_are_importable_and_runnable(tmp_path: Path) -> None:
    wf1_dir = tmp_path / "wf1"
    wf1_dir.mkdir()
    _ = _write_demand_yaml(
        wf1_dir,
        file_name="a.yaml",
        name="a",
        output_path=wf1_dir / "a.csv",
    )
    wf1 = _write_workflow_yaml(wf1_dir, file_name="wf.yaml", run_id="a", demand_file="a.yaml")
    result1 = run_workflow_public(str(wf1), allowed_modules=frozenset(["tests.fixtures"]))
    assert not result1.errors()

    wf2_dir = tmp_path / "wf2"
    wf2_dir.mkdir()
    _ = _write_demand_yaml(
        wf2_dir,
        file_name="b.yaml",
        name="b",
        output_path=wf2_dir / "b.csv",
    )
    wf2 = _write_workflow_yaml(wf2_dir, file_name="wf.yaml", run_id="b", demand_file="b.yaml")
    result2 = run_workflow_stable(str(wf2), allowed_modules=frozenset(["tests.fixtures"]))
    assert not result2.errors()


def test_injected_executor_does_not_mutate_globals_or_cross_contaminate_concurrent_runs(tmp_path: Path) -> None:
    from scalim.execution.run_ir import run_ir as real_run_ir  # noqa: PLC0415
    from scalim.workflow import execute as execute_mod  # noqa: PLC0415

    original_run_ir = execute_mod.run_ir

    wf1_dir = tmp_path / "wf1"
    wf1_dir.mkdir()
    _ = _write_demand_yaml(
        wf1_dir,
        file_name="a.yaml",
        name="a",
        output_path=wf1_dir / "a.csv",
    )
    wf1 = _write_workflow_yaml(wf1_dir, file_name="wf.yaml", run_id="a", demand_file="a.yaml")

    wf2_dir = tmp_path / "wf2"
    wf2_dir.mkdir()
    _ = _write_demand_yaml(
        wf2_dir,
        file_name="b.yaml",
        name="b",
        output_path=wf2_dir / "b.csv",
    )
    wf2 = _write_workflow_yaml(wf2_dir, file_name="wf.yaml", run_id="b", demand_file="b.yaml")

    calls = []
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def _make_fake(tag: str):  # type: ignore[no-untyped-def]
        def _fake(demand_ir, request, engine_factory=None, event_meta_defaults=None):  # type: ignore[no-untyped-def]
            with lock:
                calls.append(tag)
            barrier.wait(timeout=10.0)
            return real_run_ir(
                demand_ir,
                request,
                engine_factory=engine_factory,
                event_meta_defaults=event_meta_defaults,
            )

        return _fake

    results = {}
    errors = []

    def _run(tag: str, wf: Path, fake):  # type: ignore[no-untyped-def]
        try:
            results[tag] = run_workflow_stable(str(wf), allowed_modules=frozenset(["tests.fixtures"]), run_ir_fn=fake)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=_run, args=("a", wf1, _make_fake("a")))
    t2 = threading.Thread(target=_run, args=("b", wf2, _make_fake("b")))
    t1.start()
    t2.start()
    t1.join(timeout=30.0)
    t2.join(timeout=30.0)

    assert not t1.is_alive()
    assert not t2.is_alive()
    assert not errors
    assert not results["a"].errors()
    assert not results["b"].errors()

    assert calls.count("a") == 1
    assert calls.count("b") == 1

    assert execute_mod.run_ir is original_run_ir
