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


def test_output_composition_is_package_and_no_legacy_py_module() -> None:
    import importlib
    from pathlib import Path

    spec = importlib.util.find_spec("scalim.execution.output_composition")
    assert spec is not None
    assert spec.origin is not None
    assert spec.origin.endswith("src/scalim/execution/output_composition/__init__.py")

    legacy = Path(__file__).resolve().parents[2] / "src/scalim/execution/output_composition.py"
    assert not legacy.exists()
