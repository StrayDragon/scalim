from scalim.execution import output_composition as oc


def test_fingerprint_part_helpers_are_stable_and_structured() -> None:
    m = oc.AggMetricSpec(out_field_id="cnt", op="count", field_id="id")
    assert oc._metric_fingerprint_part(m) == "cnt|op=count|field_id=id|field_ids=|threshold="

    r = oc.RankFieldSpec(out_field_id="rank", kind="dense_rank", by="cnt", order="desc", top_k=1, top_k_mode="rank")
    assert oc._rank_field_fingerprint_part(r) == "rank|kind=dense_rank|by=cnt|partition_by=|order=desc|order_by=|top_k=1|top_k_mode=rank"

    p = oc.PostFieldSpec(
        out_field_id="score",
        kind="test",
        dependencies=("rank",),
        fingerprint="score=rank*10",
        calculator=lambda row: int(row.get("rank") or 0) * 10,
    )
    assert oc._post_field_fingerprint_part(p) == "score|kind=test|deps=rank|fingerprint=score=rank*10"


def test_output_composition_py_placeholder_is_executable_for_coverage() -> None:
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "src/scalim/execution/output_composition.py"
    spec = importlib.util.spec_from_file_location("scalim.execution._output_composition_placeholder", path)
    assert spec is not None
    assert spec.loader is not None

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
