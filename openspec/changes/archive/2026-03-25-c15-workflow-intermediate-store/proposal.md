## Why

当前 workflow 对“仅供 write nodes 消费”的 pathless CSV outputs 仍采用 run-scoped 临时 CSV 落盘，再由 write nodes 重新读取并写入 workbook/csv/sheetbook。这个路径带来了可避免的磁盘 IO、临时目录清理复杂度，以及 workflow 与 demand 之间不必要的文件系统耦合。

假设更高优先级的 `workflow-layering-refactor` 已先合并，现在适合把这段链路收敛为真正的内存中间态：保持 authoring surface 不变，但让 workflow-managed outputs 直接在内存中流转。

## What Changes

- 将 workflow-managed 的 pathless CSV outputs 从“分配临时文件路径并落盘”改为“物化为 workflow 可消费的内存 CSV artifact”。
- demand 节点在 workflow 场景下，若某个 pathless CSV output 被 write intents 引用，运行时 MUST 生成可供 write nodes 直接消费的内存中间态，而不是 `managed_temp_outputs/*.csv`。
- workflow write nodes MUST 同时支持消费两类上游 output artifact：
  - 普通文件路径 output（现有行为，保持不变）
  - workflow-managed 的内存 CSV artifact（新行为）
- standalone demand 编译/运行对 pathless CSV 的 fail-fast 约束保持不变；只有 workflow 明确托管的 output 才允许无 path。
- v1 不引入预算、spill、跨 demand source 复用或非 CSV 中间格式；这些后续优化单独放到低优先级 proposal。

## Capabilities

### New Capabilities
<!-- 无 -->

### Modified Capabilities
- `workflow-managed-temp-outputs`: pathless CSV outputs 的 workflow 托管语义从“临时文件路径 + 清理”升级为“内存中间态 + 最终消费者后释放”。
- `workflow-shared-output-containers`: write nodes 消费上游 output artifact 时，除了文件路径，还需要支持 workflow-managed 的内存 CSV artifact。
- `output-composition`: workflow 托管场景下的 pathless CSV target 需要支持行流式写入到内存 sink，并把中间结果暴露给 workflow runtime。

## Impact

- 受影响代码/入口（按 `workflow-layering-refactor` 已合并后的目标结构表述）：
  - `src/scalim/execution/output_composition.py`
  - `src/scalim/execution/run_ir.py`
  - `src/scalim/workflow/**` 或其等价 workflow runtime SSOT 模块
  - workflow 共享资源写入实现（csv/workbook/sheetbook）
  - 相关 workflow pytest 与 demo fixtures
- 用户可见影响：
  - workflow YAML 写法不变；已有 pathless CSV + writes 的 authoring surface 继续成立
  - workflow 结束后不再依赖临时 CSV 目录清理来保证无残留
- SSOT / 生成物边界：
  - 本 change 的 SSOT 为 `openspec/changes/c15-workflow-intermediate-store/**` 与后续同步到的 `openspec/specs/**/spec.md`
  - 本 change 不直接修改 `.gen.*` 文件或 `AUTOGEN` 注入区块；共享/发布前仍通过 `just openspec-check` 校验 OpenSpec 工件
