from __future__ import annotations

from dataclasses import dataclass

from scalim.planning.plan import PlanMetadata
from scalim.planning.viz import _viz_add_node, build_viz_graph_snapshot
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir.fields import DerivedFieldIr, FieldIr
from scalim.spec.ir.relations import LookupStepIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr


def test_viz_add_node_dedupes_duplicate_ids() -> None:
    nodes = []
    node_ids = set()
    _viz_add_node(nodes, node_ids, "field:a", "field", {"label": "a"})
    _viz_add_node(nodes, node_ids, "field:a", "field", {"label": "a"})
    assert len(nodes) == 1


def test_build_viz_graph_snapshot_covers_derived_unknown_ref_lookup_and_source_edges() -> None:
    main = MainSourceIr(source_id="main", loader=lambda: [])
    ref_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(callable=lambda: {}),
    )

    ref_step = LookupStepIr(
        from_field="customer_id",
        to_source=ref_source,
        bind=BindingIr(key_field="customer_id", params_builder=lambda ctx: ((), {}), mode="rows", cache_mode="batch"),
    )

    field_amount = FieldIr(field_id="amount", name="Amount", source=main)
    field_customer = FieldIr(
        field_id="customer_name",
        name="Customer",
        source=ref_source,
        lookup_steps=(ref_step,),
    )
    derived_profit = DerivedFieldIr(
        field_id="profit",
        name="Profit",
        dependencies=("amount",),
        calculator=lambda amount: amount,
    )

    @dataclass
    class _Plan:
        field_specs: dict
        field_dependencies: dict
        stages: list
        metadata: PlanMetadata
        target_fields: list

    plan = _Plan(
        field_specs={
            "amount": field_amount,
            "customer_name": field_customer,
            "profit": derived_profit,
            "weird": 123,
        },
        field_dependencies={"profit": ("amount",)},
        stages=[],
        metadata=PlanMetadata(total_fields=4),
        target_fields=["amount", "customer_name", "profit"],
    )

    snapshot = build_viz_graph_snapshot(
        plan,
        include_stage_nodes=False,
        include_loader_nodes=False,
        include_source_nodes=True,
    )

    node_ids = {node["id"] for node in snapshot["nodes"]}
    assert "field:profit" in node_ids
    assert "field:weird" in node_ids
    assert any(edge["type"] == "ref_lookup" for edge in snapshot["edges"])
