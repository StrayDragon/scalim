import logging

import pytest

from scalim.planning.loader_ordering.deps import build_ref_field_ordering_deps
from scalim.planning.loader_ordering.sorting import REF_LOADER_ORDERING_DEGRADED_PREFIX, sort_ref_loaders
from scalim.spec.ir import DemandIr
from scalim.spec.ir import FieldIr
from scalim.spec.ir import LookupStepIr
from scalim._internal.utils.graph import ScalimCyclicDependencyError

from tests.fixtures.planning_fixtures import make_main_source, make_source


def test_sort_ref_loaders_cycle_detected() -> None:
    source_a = make_source("source_a")
    source_b = make_source("source_b")

    ref_loaders = [
        (source_a, [("field_a", "field_b")]),
        (source_b, [("field_b", "field_a")]),
    ]

    with pytest.raises(ScalimCyclicDependencyError):
        sort_ref_loaders(ref_loaders)


def test_sort_ref_loaders_dependency_enforces_topological_order() -> None:
    source_a = make_source("a")
    source_b = make_source("b")

    ref_loaders = [
        (source_a, [("field_a", "field_b")]),
        (source_b, [("field_b", "")]),
    ]

    sorted_loaders = sort_ref_loaders(ref_loaders)
    assert [src.source_id for src, _ in sorted_loaders] == ["b", "a"]


def test_sort_ref_loaders_warns_and_falls_back_stably(caplog) -> None:
    source_a = make_source("a")
    source_b = make_source("b")
    source_c = make_source("c")

    missing_keys = tuple("missing_{}".format(i) for i in range(11))
    ref_loaders = [
        (source_a, [("field_a", ())]),
        (source_b, [("field_b", ())]),
        (source_c, [("field_c", ("field_b",) + missing_keys)]),
    ]

    with caplog.at_level(logging.WARNING):
        sorted_loaders = sort_ref_loaders(ref_loaders)

    assert [src.source_id for src, _ in sorted_loaders] == ["a", "b", "c"]
    warnings = [rec for rec in caplog.records if REF_LOADER_ORDERING_DEGRADED_PREFIX in rec.getMessage()]
    assert len(warnings) == 1
    assert "missing_0" in warnings[0].message
    assert ", ..." in warnings[0].message


def test_sort_ref_loaders_skips_same_loader_deps_and_covers_degree_branches(caplog) -> None:
    source_a = make_source("a")
    source_b = make_source("b")
    source_c = make_source("c")

    # `field_a2` 属于同一个 loader,依赖它不应产生 loader 依赖边.
    # 同时给 `c` 增加两个依赖,覆盖 in_degree 从 2 递减到 1 的分支.
    ref_loaders = [
        (source_a, [("field_a", "field_a2"), ("field_a2", "")]),
        (source_b, [("field_b", "")]),
        (source_c, [("field_c", ("field_a", "field_b", "missing_once"))]),
    ]

    with caplog.at_level(logging.WARNING):
        sorted_loaders = sort_ref_loaders(ref_loaders)

    assert [src.source_id for src, _ in sorted_loaders] == ["a", "b", "c"]
    warnings = [rec for rec in caplog.records if REF_LOADER_ORDERING_DEGRADED_PREFIX in rec.getMessage()]
    assert len(warnings) == 1
    assert ", ..." not in warnings[0].message


def test_build_ref_field_ordering_deps_handles_edge_cases() -> None:
    class _FakeSource:
        def __init__(self, source_id: str) -> None:
            self.source_id = source_id

    orders_source = make_main_source("orders")
    src_a = make_source("src_a")
    src_b = make_source("src_b")
    src_fake = make_source("fake")

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
        # 1) no steps -> early return
        FieldIr(field_id="empty_steps", name="Empty", source=src_a, lookup_steps=()),
        # 2) self dep -> skipped
        FieldIr(
            field_id="self_dep",
            name="Self",
            source=src_a,
            lookup_steps=(LookupStepIr(from_field="self_dep", to_source=src_a),),
        ),
        # 3) dep source not SourceIr -> skipped
        FieldIr(field_id="dep_fake", name="DepFake", source=_FakeSource("fake")),
        FieldIr(
            field_id="uses_fake",
            name="UsesFake",
            source=src_a,
            lookup_steps=(LookupStepIr(from_field="dep_fake", to_source=src_a),),
        ),
        # 4) dep is not a ref field -> skipped
        FieldIr(field_id="dep_non_ref", name="DepNonRef", source=src_b),
        FieldIr(
            field_id="uses_non_ref",
            name="UsesNonRef",
            source=src_a,
            lookup_steps=(LookupStepIr(from_field="dep_non_ref", to_source=src_a),),
        ),
        # 5) duplicate dep -> dedupe
        FieldIr(
            field_id="dep_ref",
            name="DepRef",
            source=src_b,
            lookup_steps=(LookupStepIr(from_field="order_id", to_source=src_b),),
        ),
        FieldIr(
            field_id="dupe_dep",
            name="DupeDep",
            source=src_a,
            lookup_steps=(
                LookupStepIr(from_field="dep_ref", to_source=src_a),
                LookupStepIr(from_field="dep_ref", to_source=src_a),
            ),
        ),
    ]

    demand = DemandIr.from_irs(
        sources=[src_a, src_b, src_fake],
        fields=fields,
        main_source=orders_source,
    )

    assert build_ref_field_ordering_deps(demand, "empty_steps", demand.fields["empty_steps"]) == ()
    assert build_ref_field_ordering_deps(demand, "self_dep", demand.fields["self_dep"]) == ()
    assert build_ref_field_ordering_deps(demand, "uses_fake", demand.fields["uses_fake"]) == ()
    assert build_ref_field_ordering_deps(demand, "uses_non_ref", demand.fields["uses_non_ref"]) == ()
    assert build_ref_field_ordering_deps(demand, "dupe_dep", demand.fields["dupe_dep"]) == ("dep_ref",)
