import csv
from decimal import Decimal
from pathlib import Path

from scalim.dsl.by_yaml import run


def _read_csv_rows(path: Path) -> "list[dict[str, str]]":
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_csv_header(path: Path) -> "list[str]":
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader)


def test_yaml_outputs_aggregate_fields_rank_post_fields_and_where_e2e(tmp_path: Path) -> None:
    detail_path = tmp_path / "detail_direct.csv"
    summary_path = tmp_path / "summary_direct.csv"

    yaml_path = tmp_path / "demo.demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.yaml_outputs_e2e:demo_orders_loader
  fields:
    order_id: {extract: order_id}
    channel: {extract: channel}
    customer_id: {extract: customer_id}
    amount: {extract: amount}
sources: {}
outputs:
  - name: detail_direct
    container: {type: csv, path: %s}
    fields: [order_id, channel, customer_id, amount]
    where: "channel == 'direct'"
  - name: summary_direct
    container: {type: csv, path: %s}
    where: "channel == 'direct'"
    aggregate:
      group_by: [customer_id]
      fields:
        order_cnt: {count: {}}
        sum_amount: {sum: {field: amount}}
        rank: {dense_rank: {by: sum_amount, order: desc, top_k: 1, top_k_mode: rank}}
        score: {score_by_rank: {rank_field: rank, base: 100, step: 10}}
        score2: {call_by: "tests.fixtures.yaml_outputs_e2e:score_from_rank(rank=rank, base=100, step=10)"}
"""
        % (str(detail_path), str(summary_path)),
        encoding="utf-8",
    )

    _ = run(str(yaml_path), allowed_modules=frozenset(["tests.fixtures"]))

    assert detail_path.exists()
    assert summary_path.exists()

    detail_rows = _read_csv_rows(detail_path)
    assert len(detail_rows) == 4
    assert {r.get("channel") for r in detail_rows} == {"direct"}

    summary_rows = _read_csv_rows(summary_path)
    # top_k_mode=rank expands ties: keep both c2/c3 (sum_amount=200) and drop c1 (sum_amount=120).
    assert [r.get("customer_id") for r in summary_rows] == ["c2", "c3"]
    assert [int(r.get("order_cnt") or "0") for r in summary_rows] == [1, 1]
    assert [Decimal(r.get("sum_amount") or "0") for r in summary_rows] == [Decimal("200"), Decimal("200")]
    assert [int(r.get("rank") or "0") for r in summary_rows] == [1, 1]
    assert [Decimal(r.get("score") or "0") for r in summary_rows] == [Decimal("100"), Decimal("100")]
    assert [int(r.get("score2") or "0") for r in summary_rows] == [100, 100]


def test_yaml_outputs_aggregate_allows_output_fields_order_and_aggregate_names_e2e(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary_direct.csv"

    yaml_path = tmp_path / "demo.demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.yaml_outputs_e2e:demo_orders_loader
  fields:
    channel: {extract: channel}
    customer_id: {extract: customer_id, name: 客户}
    amount: {extract: amount}
sources: {}
outputs:
  - name: summary_direct
    container: {type: csv, path: %s, header_fields_output_by: name}
    where: "channel == 'direct'"
    aggregate:
      group_by: [customer_id]
      fields:
        order_cnt: {name: 订单量, count: {}}
        sum_amount: {name: GMV, sum: {field: amount}}
        rank: {name: 排名, dense_rank: {by: sum_amount, order: desc}}
    fields: [rank, customer_id, order_cnt, sum_amount]
"""
        % str(summary_path),
        encoding="utf-8",
    )

    _ = run(str(yaml_path), allowed_modules=frozenset(["tests.fixtures"]))

    assert summary_path.exists()
    assert _read_csv_header(summary_path) == ["排名", "客户", "订单量", "GMV"]
