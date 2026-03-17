import pytest

from scalim.execution.derived_outputs import PostFieldSpec, RankFieldSpec, build_finalize_dag_plan


def _post(*, out_field_id: str, deps=()):  # type: ignore[no-untyped-def]
    return PostFieldSpec(
        out_field_id=out_field_id,
        kind="test",
        dependencies=tuple(deps),
        fingerprint="",
        calculator=lambda _row: None,
    )


def test_build_finalize_dag_plan_rank_by_compute_puts_compute_before_rank_and_in_pre_top_k() -> None:
    plan = build_finalize_dag_plan(
        rank_fields=(RankFieldSpec(out_field_id="rank", kind="dense_rank", by="ratio", order="desc"),),
        post_fields=(
            PostFieldSpec(
                out_field_id="ratio",
                kind="compute",
                dependencies=("sum_amount", "order_cnt"),
                fingerprint="sum_amount / order_cnt",
                calculator=lambda _row: None,
            ),
        ),
    )

    assert [i.out_field_id for i in plan.items] == ["ratio", "rank"]
    assert plan.pre_top_k_ids == ("ratio", "rank")
    assert plan.post_top_k_ids == ()


def test_build_finalize_dag_plan_rank_after_post_is_supported_and_interleaves_rank_and_post_in_pre_top_k() -> None:
    # rank1 -> score1 -> rank2
    plan = build_finalize_dag_plan(
        rank_fields=(
            RankFieldSpec(out_field_id="rank1", kind="dense_rank", by="cnt", order="desc"),
            RankFieldSpec(out_field_id="rank2", kind="dense_rank", by="score1", order="desc"),
        ),
        post_fields=(
            PostFieldSpec(
                out_field_id="score1",
                kind="score_by_rank",
                dependencies=("rank1",),
                fingerprint="",
                calculator=lambda _row: None,
            ),
            _post(out_field_id="after_top_k", deps=("cnt",)),
        ),
    )

    assert [i.out_field_id for i in plan.items] == ["rank1", "score1", "rank2", "after_top_k"]
    assert plan.pre_top_k_ids == ("rank1", "score1", "rank2")
    assert plan.post_top_k_ids == ("after_top_k",)


def test_build_finalize_dag_plan_stable_topo_order_sorts_independent_nodes_by_out_field_id() -> None:
    plan = build_finalize_dag_plan(rank_fields=(), post_fields=(_post(out_field_id="b"), _post(out_field_id="a")))
    assert [i.out_field_id for i in plan.items] == ["a", "b"]


def test_build_finalize_dag_plan_cycle_detection_raises_actionable_error() -> None:
    with pytest.raises(ValueError, match=r"cyclic dependency"):
        _ = build_finalize_dag_plan(
            rank_fields=(),
            post_fields=(
                _post(out_field_id="a", deps=("b",)),
                _post(out_field_id="b", deps=("a",)),
            ),
        )
