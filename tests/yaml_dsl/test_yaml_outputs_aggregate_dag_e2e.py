import csv
from decimal import Decimal
from pathlib import Path
from textwrap import dedent

from scalim.dsl.yaml_dsl import RunOptions, run
from tests.support.yaml_fixtures import make_yaml_config


def _read_csv_rows(path: Path) -> "list[dict[str, str]]":
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_yaml_outputs_aggregate_derived_fields_dag_gap01_to_03_e2e(tmp_path: Path) -> None:
    # Covers downstream gap01~03:
    # - rank.by can reference compute derived field (rank-by-compute)
    # - post field can depend on post field (post-depends-on-post)
    # - rank can reference post derived field (rank-after-post)
    out_root = tmp_path / "out"

    yaml_content = make_yaml_config(
        name="demo",
        main_source="""
source_id: orders
loader: tests.fixtures.yaml_outputs_e2e:demo_orders_loader
fields:
  order_id: {extract: order_id}
  channel: {extract: channel}
  customer_id: {extract: customer_id}
  amount: {extract: amount}
""",
        sources="{}",
    )
    yaml_content += dedent(
        f"""
resources:
  files:
    summary_csv:
      kind: csv_file
      path: "{out_root}"
outputs:
  - name: summary
    to: {{file: summary_csv}}
    where: "channel == 'direct'"
    aggregate:
      group_by: [customer_id]
      fields:
        order_cnt:
          count: {{}}
        sum_amount:
          sum: {{field: amount}}

        # gap01: compute then rank-by-compute
        avg_amount:
          compute: "sum_amount / order_cnt"
        rank_by_avg:
          dense_rank: {{by: avg_amount, order: desc}}

        # gap02: post can depend on post (score2 depends on score1)
        score1:
          score_by_rank: {{rank_field: rank_by_avg, base: 100, step: 10}}
        score2:
          call_by: "tests.fixtures.call_by_fns:add(a=score1, b=5)"
        all_integral:
          compute: "score1 + score2"

        # gap03: rank-after-post
        final_rank:
          dense_rank: {{by: all_integral, order: desc, top_k: 1, top_k_mode: rank}}

        # Not needed by any rank: should be evaluated after top_k on filtered rows.
        after_top_k:
          compute: "score2 + 1"

    fields: [customer_id, order_cnt, sum_amount, avg_amount, rank_by_avg, score1, score2, all_integral, final_rank, after_top_k]
"""
    )

    yaml_path = tmp_path / "demo.demand.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")

    result = run(str(yaml_path), options=RunOptions(allowed_modules=frozenset(["tests.fixtures"])))

    assert result.output_path is not None
    out_path = Path(str(result.output_path))
    assert out_path.exists()

    from scalim.execution.versioned_outputs import parse_versioned_output_path  # noqa: PLC0415

    parsed = parse_versioned_output_path(out_path)
    assert parsed.root == out_root.resolve(strict=False)
    assert parsed.kind == "files"
    assert parsed.artifact_id == "summary_csv"

    rows = _read_csv_rows(out_path)
    # top_k_mode=rank expands ties: keep both c2/c3 and drop c1.
    assert [r.get("customer_id") for r in rows] == ["c2", "c3"]
    assert [int(r.get("order_cnt") or "0") for r in rows] == [1, 1]
    assert [Decimal(r.get("sum_amount") or "0") for r in rows] == [Decimal("200"), Decimal("200")]
    assert [Decimal(r.get("avg_amount") or "0") for r in rows] == [Decimal("200"), Decimal("200")]
    assert [int(r.get("rank_by_avg") or "0") for r in rows] == [1, 1]
    assert [Decimal(r.get("score1") or "0") for r in rows] == [Decimal("100"), Decimal("100")]
    assert [Decimal(r.get("score2") or "0") for r in rows] == [Decimal("105"), Decimal("105")]
    assert [Decimal(r.get("all_integral") or "0") for r in rows] == [Decimal("205"), Decimal("205")]
    assert [int(r.get("final_rank") or "0") for r in rows] == [1, 1]
    assert [Decimal(r.get("after_top_k") or "0") for r in rows] == [Decimal("106"), Decimal("106")]
