## Why

当前 workflow cache pool 的对外 preset `WorkflowCachePoolPreloadForeverShared(max_entries=16)` 只有“有限预算”这一个表达方式；当用户希望在大 workflow 中启用 cache pool
但不想被预算限制时，常见做法是填一个极大值来“模拟无限”。这导致 authoring 冗余、语义不清晰、并且难以通过类型/枚举层面约束出“无限 vs 有限”的正确选择。

同时，bounded preset 的默认值 `16` 也容易在没有显式意图的情况下引入隐式限制，给调参/排障带来额外成本。

## What Changes

- 新增一个显式 preset：`WorkflowCachePoolPreloadForeverUnlimited()`，用于表达“启用 cache pool 且不施加 entries 数量预算”。
- 调整 bounded preset：`WorkflowCachePoolPreloadForeverShared` 的 `max_entries` 改为 **必填**（移除默认 `16`）以减少隐式行为。**BREAKING**
- 运行时语义对齐：
  - unlimited preset 默认等价“全部 pin 到 workflow_end”（不做 DAG refcount 提前释放），避免用户在 unlimited 场景仍需要理解 pin 语义。
  - bounded preset 继续支持 `pin`，用于“有限 + pin”的正交组合。
- 同步更新：实现/测试/文档与规范（OpenSpec）以覆盖新 preset 与默认行为变化。

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `workflow-cache-pool`: 新增 unlimited preset 的对外配置面与其预算/生命周期语义；并调整 bounded preset 的 `max_entries` 默认行为（由默认值变为显式必填）。

## Impact

- Public API / types:
  - `src/scalim/dsl/yaml_dsl/workflow_types.py`：新增 preset；`WorkflowCachePoolPreloadForeverShared` 构造签名变更（BREAKING）。
- Compile/runtime:
  - `src/scalim/dsl/yaml_dsl/workflow_compile.py`：runtime preset → IR 的映射与校验规则扩展。
  - `src/scalim/execution/workflow_cache_pool.py`：unlimited 预算与 workflow_end 生命周期语义。
- Specs/docs/tests:
  - `openspec/specs/workflow-cache-pool/spec.md`：requirements 更新。
  - `docs/doc/yaml-dsl/workflow.md`、相关示例与 notebooks：示例更新（不再推荐“大数=无限”）。
  - `tests/**`：覆盖新 preset、以及 bounded preset “必须显式 max_entries” 的行为。
