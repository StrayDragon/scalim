---
depends_on: []
blocks:
  - c30-workflow-shared-book-memory
---

# c20-book-write-policy-python-ssot

## Why

YAML DSL 应逐步收敛为**编排与资源 identity**（runs、依赖、`resources.books/files` 的 id/variant/path、`outputs.to` 绑定），避免把可调参策略堆进 YAML 导致维护混乱。

当前 `resources.books.*.write_defaults` 与 `xlsx_memory.budget` 仍是 YAML SSOT，与上位原则冲突：

- `governance-mainline-principles`：环境/性能预算类 knobs 应收口到 Python/CLI
- `yaml-dsl-runtime-policy-boundary`：已迁出 `workflow.options.*`，但未覆盖 book 写策略/budget
- `yaml-dsl-write-policy-and-output-extras`：purpose 写「迁出 write policy」，r2 却把 `write_defaults` 留在 YAML（内部矛盾）

产品决策（2026-07-12 会话 SSOT）：

1. **资源声明留 YAML**（id / oneOf variant / path / `export_xlsx.path` 骨架）
2. **`write_defaults` + `budget` → Python SSOT**（选项①）；开箱使用 builtin defaults
3. **`allow_formulas` / `encoding` 暂保持 YAML 可写**（通常不动态改）

进度追踪：仓库根 `_HANDOFF.md`。

## What Changes

### BREAKING（YAML authoring）

- YAML 中出现 `resources.books.*.write_defaults` MUST fail-fast，并给出迁移到 Python typed policy 的提示
- YAML 中出现 `resources.books.*.xlsx_memory.budget`（及等价 budget 字段）MUST fail-fast，并给出迁移提示

### Runtime / API

- 引入 book 级 **Python SSOT**（名称在 design 收敛，示意：`BookWritePolicy` / `ResourcesPolicy`），挂到 `WorkflowRunOptions`（及 demand 单跑等价入口如需要）
- **Builtin defaults** 开箱即用（等价今日缺省：`mode=sheet`, `on_conflict=error`, `align_by=field_id`, `header_policy=once`, `on_mismatch=error`；budget 缺省 unlimited）
- 需要 `mode=append` 等同 sheet 合并语义时，MUST 通过 Python policy 显式配置
- `RunOverrides.resources` 不再以「YAML 形 overlay 补丁 write_defaults/budget」作为主路径；策略走 policy API（design 定义是否保留短暂兼容层）

### Specs / docs

- 改写 write-policy 四层模型：resources 声明（YAML）/ write+budget policy（Python）/ outputs 编排（YAML）/ extras（Python）
- 更新 docs capability-matrix / workflow 文档 / review-checklist；标 stale：`notplan/c0-roadmap-yaml-dsl-oneof-checklist`

### 明确不做（本 change）

- 不改 plan→accumulate→commit 内存模型（见下游 `workflow-shared-book-memory`）
- 不把 streaming flush knobs 引入 YAML
- 不翻转 `allow_formulas` 默认值（见独立 `allow-formulas-safe-default`）

## Capabilities

### Modified Capabilities

- `yaml-dsl-runtime-policy-boundary` — 将 `write_defaults`/`budget` 列入 runtime policy 迁出清单
- `yaml-dsl-write-policy-and-output-extras` — write policy SSOT 改为 Python；修正 purpose↔r2 矛盾
- `yaml-dsl-books-resources` — YAML books 表面去掉 write_defaults/budget
- `workflow-shared-output-containers` — 写入策略来源改为 effective Python policy
- `yaml-dsl-output-overrides` — 收缩 resources overlay：不再把 write_defaults/budget 当作 YAML 形主 SSOT

## Impact

- **代码区域**: `src/scalim/dsl/yaml_dsl/`（schema/models/validate/compile）、`workflow_types` / runtime options、`workflow/resource_defs` 装配、docs/skills/tests
- **破坏性**: **BREAKING** — 现有在 YAML 写 `write_defaults`/`budget` 的配置必须迁到 Python
- **生成物**: schema `.gen.json` 经 `just gen-yaml-dsl-schema`（或项目约定入口）刷新；禁止手改
- **依赖**: 本 change **blocks** `workflow-shared-book-memory`（后者依赖 Python budget/policy 入口）

## Examples（目标态）

### YAML（瘦编排）

```yaml
workflow:
  resources:
    books:
      report:
        xlsx_file:
          path: ./out
  runs:
    - id: a
      demand: ./a.yaml
    - id: b
      demand: ./b.yaml
      depends_on: [a]
```

### Python（SSOT；示意 API）

```python
from scalim.dsl.yaml_dsl import DemandRunOptions, WorkflowRunOptions, run_workflow
# 正式类型名以 design/实现为准

result = run_workflow(
    "workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(...),
        # resources_policy=ResourcesPolicy(books={
        #     "report": BookWritePolicy(mode="append", header_policy="once"),
        #     # budget=BookBudgetPolicy(max_sheets=16, max_total_cells=2_000_000),
        # }),
    ),
)
```
