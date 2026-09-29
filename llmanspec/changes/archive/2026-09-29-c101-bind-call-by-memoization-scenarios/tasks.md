# Tasks

实施边界：seam 为 spec 的 `specs.check_command`（`just test`，`uv run pytest tests/ -q`）；场景文本对应既有 `tests/execution/test_call_by_memoization_executor.py` / `test_call_by_memoization_filter.py` 已覆盖的行为，本 change 不新增代码与测试文件。

## T1 落地 r33/r277 嵌套场景

- [x] 在绑定分支编辑 `llmanspec/specs/execution-call-by-memoization.feature`：r33 块内补 2 个嵌套 `场景:`（开关未设置/非正整数 → 不产生控制器；正整数 N → 仅 ctx-free 字段成为候选且每字段容量 N）；r277 块内补 2 个嵌套 `场景:`（deny 优先排除；allow 非空仅匹配者入选），并修复该决策表第三行缺失的表尾 `|`。
- 验收：`llman-sdd spec unbound --limit 0` 中 `execution-call-by-memoization` 归 0；`llman-sdd validate c101-bind-call-by-memoization-scenarios --strict` 通过（含 `just test` 整批执行）。

## T2 门禁复核（在绑定分支、相对 merge-base 测量） [blocked-by: T1]

- [x] `just llmanspec-check` 通过；`llman-sdd review` 中 `execution-call-by-memoization` 的 unbound 信号为 0、criticalCount 0。
