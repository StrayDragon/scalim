"""utils 模块测试"""

import pytest
from typing import Dict, List

from scalim.utils.graph import (
    CyclicDependencyError,
    DependencyGraph,
    collect_dependencies,
    compute_levels,
    detect_cycles,
    group_by_level,
    topological_sort,
)


# region 测试: collect_dependencies


class TestCollectDependencies:
    """依赖收集测试"""

    def test_simple_deps(self) -> None:
        """测试简单依赖收集"""
        deps = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}
        result = collect_dependencies(["a"], lambda x: deps.get(x, []))
        assert result == {"a", "b", "c", "d"}

    def test_no_deps(self) -> None:
        """测试无依赖节点"""
        deps: Dict[str, List[str]] = {"a": [], "b": []}
        result = collect_dependencies(["a"], lambda x: deps.get(x, []))
        assert result == {"a"}

    def test_multiple_targets(self) -> None:
        """测试多个目标"""
        deps = {"a": ["c"], "b": ["d"], "c": [], "d": []}
        result = collect_dependencies(["a", "b"], lambda x: deps.get(x, []))
        assert result == {"a", "b", "c", "d"}

    def test_shared_deps(self) -> None:
        """测试共享依赖"""
        deps = {"a": ["c"], "b": ["c"], "c": []}
        result = collect_dependencies(["a", "b"], lambda x: deps.get(x, []))
        assert result == {"a", "b", "c"}

    def test_exclude_target(self) -> None:
        """测试不包含目标节点"""
        deps = {"a": ["b", "c"], "b": [], "c": []}
        result = collect_dependencies(["a"], lambda x: deps.get(x, []), include_target=False)
        assert result == {"b", "c"}


# endregion


# region 测试: detect_cycles


class TestDetectCycles:
    """循环检测测试"""

    def test_no_cycles(self) -> None:
        """测试无循环"""
        deps = {"a": ["b"], "b": ["c"], "c": []}
        result = detect_cycles(["a", "b", "c"], lambda x: deps.get(x, []))
        assert result == []

    def test_simple_cycle(self) -> None:
        """测试简单循环"""
        deps = {"a": ["b"], "b": ["a"]}
        result = detect_cycles(["a", "b"], lambda x: deps.get(x, []))
        assert len(result) >= 1
        # 循环应该包含 a 和 b
        cycle = result[0]
        assert "a" in cycle
        assert "b" in cycle

    def test_self_cycle(self) -> None:
        """测试自循环"""
        deps = {"a": ["a"]}
        result = detect_cycles(["a"], lambda x: deps.get(x, []))
        assert len(result) >= 1


# endregion


# region 测试: topological_sort


class TestTopologicalSort:
    """拓扑排序测试"""

    def test_simple_sort(self) -> None:
        """测试简单排序"""
        deps = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}
        result = topological_sort(["a", "b", "c", "d"], lambda x: deps.get(x, []))

        # 验证顺序: 依赖在前
        assert result.index("d") < result.index("b")
        assert result.index("b") < result.index("a")
        assert result.index("c") < result.index("a")

    def test_no_deps(self) -> None:
        """测试无依赖"""
        deps: Dict[str, List[str]] = {"a": [], "b": [], "c": []}
        result = topological_sort(["a", "b", "c"], lambda x: deps.get(x, []))
        assert set(result) == {"a", "b", "c"}

    def test_linear_deps(self) -> None:
        """测试线性依赖"""
        deps = {"a": ["b"], "b": ["c"], "c": []}
        result = topological_sort(["a", "b", "c"], lambda x: deps.get(x, []))
        assert result == ["c", "b", "a"]

    def test_cycle_raises(self) -> None:
        """测试循环依赖抛出异常"""
        deps = {"a": ["b"], "b": ["a"]}
        with pytest.raises(CyclicDependencyError):
            topological_sort(["a", "b"], lambda x: deps.get(x, []))


# endregion


# region 测试: compute_levels


class TestComputeLevels:
    """层级计算测试"""

    def test_simple_levels(self) -> None:
        """测试简单层级"""
        deps = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}
        result = compute_levels(["a", "b", "c", "d"], lambda x: deps.get(x, []))

        assert result["c"] == 0
        assert result["d"] == 0
        assert result["b"] == 1
        assert result["a"] == 2

    def test_no_deps_level(self) -> None:
        """测试无依赖节点层级为 0"""
        deps: Dict[str, List[str]] = {"a": [], "b": []}
        result = compute_levels(["a", "b"], lambda x: deps.get(x, []))

        assert result["a"] == 0
        assert result["b"] == 0


# endregion


# region 测试: group_by_level


class TestGroupByLevel:
    """层级分组测试"""

    def test_simple_groups(self) -> None:
        """测试简单分组"""
        deps = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}
        result = group_by_level(["a", "b", "c", "d"], lambda x: deps.get(x, []))

        assert len(result) == 3
        assert set(result[0]) == {"c", "d"}  # level 0
        assert result[1] == ["b"]  # level 1
        assert result[2] == ["a"]  # level 2


# endregion


# region 测试: DependencyGraph


class TestDependencyGraph:
    """DependencyGraph 类测试"""

    def test_add_and_get(self) -> None:
        """测试添加和获取"""
        graph: DependencyGraph[str] = DependencyGraph()
        graph.add_node("a", ["b", "c"])
        graph.add_node("b", ["d"])
        graph.add_node("c")
        graph.add_node("d")

        assert graph.get_deps("a") == ["b", "c"]
        assert graph.get_deps("b") == ["d"]
        assert graph.get_deps("c") == []
        assert graph.nodes() == {"a", "b", "c", "d"}

    def test_collect_deps(self) -> None:
        """测试依赖收集"""
        graph: DependencyGraph[str] = DependencyGraph()
        graph.add_node("a", ["b", "c"])
        graph.add_node("b", ["d"])
        graph.add_node("c")
        graph.add_node("d")

        result = graph.collect_deps(["a"])
        assert result == {"a", "b", "c", "d"}

    def test_topological_sort(self) -> None:
        """测试拓扑排序"""
        graph: DependencyGraph[str] = DependencyGraph()
        graph.add_node("a", ["b"])
        graph.add_node("b", ["c"])
        graph.add_node("c")

        result = graph.topological_sort()
        assert result == ["c", "b", "a"]

    def test_compute_levels_and_group_by_level(self) -> None:
        """测试层级计算与分组"""
        graph: DependencyGraph[str] = DependencyGraph()
        graph.add_node("a", ["b", "c"])
        graph.add_node("b", ["d"])
        graph.add_node("c")
        graph.add_node("d")

        levels = graph.compute_levels()
        groups = graph.group_by_level()

        assert levels["c"] == 0
        assert levels["d"] == 0
        assert "a" in groups[-1]

    def test_detect_cycles_skips_unknown_nodes(self) -> None:
        """覆盖 detect_cycles 对未知节点的跳过"""

        class _Weird:
            def __init__(self, name: str) -> None:
                self.name = name

            def __hash__(self) -> int:
                return 1

            def __eq__(self, _other: object) -> bool:
                return False

        node = _Weird("a")
        cycles = detect_cycles([node], lambda _n: [])
        assert cycles == []

    def test_detect_cycles_skips_unknown_nodes_from_iter(self) -> None:
        """覆盖 detect_cycles 对未知节点的防御分支"""

        class _UnstableHashNode:
            def __init__(self) -> None:
                self._calls = 0

            def __hash__(self) -> int:
                # set(nodes) inserts with one hash, later membership probes use a different hash.
                self._calls += 1
                return self._calls

            def __eq__(self, other: object) -> bool:
                return self is other

        cycles = detect_cycles([_UnstableHashNode()], lambda _n: [])
        assert cycles == []


# endregion
