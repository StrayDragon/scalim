"""图算法工具模块.

提供拓扑排序、循环检测、依赖收集等通用图算法.

注意: `Python 3.9+` 提供了 `graphlib.TopologicalSorter`.
如果项目最低 `Python` 版本升级到 `3.9+`,可以考虑使用 `graphlib.TopologicalSorter` 替换
本模块中的 `topological_sort` 函数,以获得更好的性能和更简洁的代码.

参考: `https://docs.python.org/3/library/graphlib.html`

当前实现保持对 `Python 3.6+` 的兼容性.

注意(FR012): `group_by_level` 和 `DependencyGraph` 当前未在 `src/scalim/` 主源码中使用,
但作为 FR012 (并行计划) 的预留接口保留.同一层级的节点没有相互依赖,可以并行处理.
"""

# region imports

import heapq
from typing import Callable, Dict, Generic, Hashable, Iterable, List, Optional, Sequence, Set, Tuple, TypeVar

# endregion

T = TypeVar("T", bound=Hashable)


def _stable_tie_break_key(node: Hashable) -> str:
    if isinstance(node, str):
        return node
    return "{}:{}".format(type(node).__name__, repr(node))


class CyclicDependencyError(Exception):
    """循环依赖异常"""

    cycles: Sequence[Sequence[Hashable]]

    def __init__(self, message: str, cycles: Optional[Sequence[Sequence[Hashable]]] = None) -> None:
        super().__init__(message)
        self.cycles = cycles or []


def collect_dependencies(
    targets: Iterable[T],
    get_deps: Callable[[T], Iterable[T]],
    *,
    include_target: bool = True,
) -> Set[T]:
    """从目标节点递归收集所有依赖.

    参数:
        `targets`: 目标节点列表
        `get_deps`: 获取节点依赖的函数
        `include_target`: 是否包含目标节点本身

    返回:
        所有依赖节点的集合

    示例:
        - `deps = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}`
        - `collect_dependencies(["a"], lambda x: deps.get(x, []))`
        - `{"a", "b", "c", "d"}`
    """
    visited: Set[T] = set()

    def dfs(node: T) -> None:
        if node in visited:
            return
        visited.add(node)
        for dep in get_deps(node):
            dfs(dep)

    for target in targets:
        if include_target:
            dfs(target)
        else:
            for dep in get_deps(target):
                dfs(dep)

    return visited


def detect_cycles(
    nodes: Iterable[T],
    get_deps: Callable[[T], Iterable[T]],
) -> List[List[T]]:
    node_set = set(nodes)
    cycles: List[List[T]] = []
    visited: Set[T] = set()
    rec_stack: Set[T] = set()

    def dfs(node: T, path: List[T]) -> None:
        if node not in node_set:
            return

        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for dep in get_deps(node):
            if dep not in node_set:
                continue
            if dep not in visited:
                dfs(dep, path)
            elif dep in rec_stack:
                cycle_start = path.index(dep)
                cycle = [*path[cycle_start:], dep]
                cycles.append(cycle)

        _ = path.pop()
        rec_stack.remove(node)

    for node in node_set:
        if node not in visited:
            dfs(node, [])

    return cycles


def topological_sort(
    nodes: Iterable[T],
    get_deps: Callable[[T], Iterable[T]],
) -> List[T]:
    """拓扑排序.

    使用卡恩算法实现, 预先构建反向依赖图以获得 O(n+e) 复杂度.
    依赖在前,被依赖者在后.依赖方向约定为: A 依赖 B 表示 A -> B.

    参数:
        `nodes`: 要排序的节点集合
        `get_deps`: 获取节点依赖的函数 (返回当前节点依赖的节点)

    返回:
        拓扑排序后的节点列表.同层级节点的相对顺序保证稳定:
        当多个节点在同一层级同时就绪时,会按稳定的“平局规则”输出(默认使用节点的稳定字符串表示).

    异常:
        `CyclicDependencyError`: 检测到循环依赖

    示例:
        - `deps = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}`
        - `topological_sort(["a", "b", "c", "d"], lambda x: deps.get(x, []))`
        - `["c", "d", "b", "a"]`  # `c`,`d` 无依赖,先输出; `b` 依赖 `d`; `a` 依赖 `b`,`c`
    """
    node_set = set(nodes)
    if not node_set:
        return []

    ordered_nodes = sorted(node_set, key=_stable_tie_break_key)
    node_rank: Dict[T, int] = {node: idx for idx, node in enumerate(ordered_nodes)}

    # 计算入度和反向依赖 (预计算以获得 O(n+e) 复杂度)
    # 注意: 这里的"依赖"是指 A 依赖 B,则 A -> B
    # 入度是指 A 有多少个依赖; 反向依赖是指 B 被哪些节点依赖
    in_degree: Dict[T, int] = dict.fromkeys(ordered_nodes, 0)
    reverse_deps: Dict[T, List[T]] = {node: [] for node in ordered_nodes}

    for node in ordered_nodes:
        for dep in get_deps(node):
            if dep in node_set:
                # `node` 依赖 `dep`,所以 `node` 的入度 +1, `dep` 的反向依赖加上 `node`
                in_degree[node] += 1
                reverse_deps[dep].append(node)

    ready: List[Tuple[int, T]] = [(node_rank[node], node) for node in ordered_nodes if in_degree[node] == 0]
    heapq.heapify(ready)
    result: List[T] = []

    while ready:
        _rank, current = heapq.heappop(ready)
        result.append(current)

        # O(1) 查找反向依赖, 而非遍历所有节点
        for dependent in reverse_deps[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                heapq.heappush(ready, (node_rank[dependent], dependent))

    if len(result) != len(node_set):
        cycles = detect_cycles(node_set, get_deps)
        msg = "检测到循环依赖"
        raise CyclicDependencyError(msg, cycles)

    return result


def compute_levels(
    nodes: Iterable[T],
    get_deps: Callable[[T], Iterable[T]],
    sorted_nodes: Optional[List[T]] = None,
) -> Dict[T, int]:
    """计算每个节点的依赖层级.

    层级 0 表示无依赖,层级 N 表示最长依赖链长度为 N.

    参数:
        `nodes`: 节点集合
        `get_deps`: 获取节点依赖的函数
        `sorted_nodes`: 可选的已排序节点列表 (避免重复排序)

    返回:
        节点到层级的映射

    示例:
        - `deps = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}`
        - `compute_levels(["a", "b", "c", "d"], lambda x: deps.get(x, []))`
        - `{"c": 0, "d": 0, "b": 1, "a": 2}`
    """
    if sorted_nodes is None:
        sorted_nodes = topological_sort(nodes, get_deps)

    node_set = set(nodes)
    levels: Dict[T, int] = {}

    for node in sorted_nodes:
        deps = [d for d in get_deps(node) if d in node_set]
        if not deps:
            levels[node] = 0
        else:
            max_dep_level = max((levels.get(dep, 0) for dep in deps), default=0)
            levels[node] = max_dep_level + 1

    return levels


def group_by_level(
    nodes: Iterable[T],
    get_deps: Callable[[T], Iterable[T]],
) -> List[List[T]]:
    """按依赖层级分组节点.

    同一层级的节点可以并行处理.
    分组内节点顺序与 `topological_sort` 的稳定性一致(同层按稳定“平局规则”),保证可重复.

    参数:
        `nodes`: 节点集合
        `get_deps`: 获取节点依赖的函数

    返回:
        按层级分组的节点列表,索引即为层级

    示例:
        - `deps = {"a": ["b", "c"], "b": ["d"], "c": [], "d": []}`
        - `group_by_level(["a", "b", "c", "d"], lambda x: deps.get(x, []))`
        - `[["c", "d"], ["b"], ["a"]]`
    """
    sorted_nodes = topological_sort(nodes, get_deps)
    levels = compute_levels(nodes, get_deps, sorted_nodes)

    # 找出最大层级
    max_level = max(levels.values()) if levels else 0

    # 按层级分组
    groups: List[List[T]] = [[] for _ in range(max_level + 1)]
    for node in sorted_nodes:
        level = levels[node]
        groups[level].append(node)

    return groups


class DependencyGraph(Generic[T]):
    """依赖图封装类: 提供便捷的依赖图操作接口"""

    _adjacency: Dict[T, List[T]]

    def __init__(self) -> None:
        """初始化空图"""
        self._adjacency = {}

    def add_node(self, node: T, deps: Optional[Iterable[T]] = None) -> None:
        """添加节点及其依赖.

        参数:
            `node`: 节点
            `deps`: 该节点依赖的节点列表
        """
        self._adjacency[node] = list(deps) if deps else []

    def get_deps(self, node: T) -> List[T]:
        """获取节点的依赖"""
        return self._adjacency.get(node, [])

    def nodes(self) -> Set[T]:
        """获取所有节点"""
        return set(self._adjacency.keys())

    def collect_deps(self, targets: Iterable[T]) -> Set[T]:
        """收集目标节点的所有依赖"""
        return collect_dependencies(targets, self.get_deps)

    def detect_cycles(self) -> List[List[T]]:
        """检测循环依赖"""
        return detect_cycles(self._adjacency.keys(), self.get_deps)

    def topological_sort(self) -> List[T]:
        """拓扑排序"""
        return topological_sort(self._adjacency.keys(), self.get_deps)

    def compute_levels(self) -> Dict[T, int]:
        """计算层级"""
        return compute_levels(self._adjacency.keys(), self.get_deps)

    def group_by_level(self) -> List[List[T]]:
        """按层级分组"""
        return group_by_level(self._adjacency.keys(), self.get_deps)
