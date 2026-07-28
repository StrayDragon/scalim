# 2026-07-12: book-write-policy-python-ssot

> **NOTE（后续 BREAKING）**：`BookBudgetPolicy` 已在 `2026-07-28-remove-book-budget-policy` 移除；勿再抄 After 中的 budget 示例。当前 budget 迁移：删除 YAML/`RunOverrides`/`ResourcesPolicy` 中的 budget 字段（见该 upgrade）。

> **身份说明（2026-07-20）**：下文 Before/After 示例仍可能出现历史 `xlsx_file` / `xlsx_memory` 作为当时 identity 写法；当前唯一 authoring 为 `xlsx`（可选 `path`），见 `2026-07-20-remove-deprecated-xlsx-file-memory-kinds.md`。本批次的核心合约（write 迁出 YAML）仍然有效；budget 面已被后续批次删除。

## 变更摘要

本批次做一次性 **BREAKING** 边界收敛: book 级写入策略与内存 budget 迁出 YAML authoring，改为 Python runtime policy SSOT。

> 复制示例时只抄 **After** 段落；文中 `Before` 块里的 `write_defaults` / `BookWriteDefaultsOverride` / `BookBudgetOverride` 是故意展示的旧写法，不可再用于新代码。

- **BREAKING**: YAML `resources.books.*.write_defaults` 已移除（出现即 fail-fast + 迁移提示）
- **BREAKING**: YAML `resources.books.*.xlsx_memory.budget` 已移除（出现即 fail-fast + 迁移提示）
- **BREAKING**: `BookResourceOverride` / `RunOverrides.resources` 不再接受 `write_defaults` / `budget` overlay
- **BREAKING**: public facade 不再导出 `BookWriteDefaultsOverride` / `BookBudgetOverride`
- **NEW**: `ResourcesPolicy` / `BookResourcePolicy` / `BookWritePolicy` / `BookBudgetPolicy`（及对应 StrEnum）
- 挂载点:
  - `WorkflowRunOptions.resources_policy`
  - `DemandRunOptions.resources_policy`
- 省略 policy 时行为与旧 YAML 缺省一致（`mode=sheet`、`header_policy=once`、…；budget unlimited）
- YAML 仍保留 book identity：当时为 `xlsx_file` / `xlsx_memory` + `path` / `export_xlsx.path`（`allow_formulas` 暂留 YAML）
- **后续 authoring 收敛**：统一 `xlsx`（可选 `path`）见 `2026-07-13-unified-xlsx-book-kind.md`

本批次 **不提供兼容层/弃用期**：旧 YAML 字段与旧 override 类型会直接失效。

对应 llmanspec change:
- `llmanspec/changes/archive/2026-07-12-c20-book-write-policy-python-ssot/`

对应主规范(节选):
- `llmanspec/specs/yaml-dsl-books-resources/spec.toon`
- `llmanspec/specs/yaml-dsl-write-policy-and-output-extras/spec.toon`
- `llmanspec/specs/yaml-dsl-runtime-policy-boundary/spec.toon`
- `llmanspec/specs/workflow-shared-output-containers/spec.toon`

下游同步盘点:
- 仅用于盘点与行动: `.tmp/known-outer-paths-using-this-package.txt`（请勿在公开输出中复述其内容）

## Migration Checklist

### 1) 删除 YAML `write_defaults` / `xlsx_memory.budget`

Before:

```yaml
resources:
  books:
    report:
      xlsx_file:
        path: ./out
      write_defaults:
        mode: append
        header_policy: once
```

或:

```yaml
resources:
  books:
    report:
      xlsx_memory:
        budget: {max_sheets: 8, max_total_cells: 1000000}
        export_xlsx: {path: ./out}
```

After（YAML 只留 identity）:

```yaml
resources:
  books:
    report:
      xlsx_file:
        path: ./out
```

```yaml
resources:
  books:
    report:
      xlsx_memory:
        export_xlsx: {path: ./out}
```

### 2) 在 Python 入口配置 policy

```python
from scalim.dsl.yaml_dsl import (
    BookBudgetPolicy,
    BookResourcePolicy,
    BookWriteHeaderPolicy,
    BookWriteMode,
    BookWritePolicy,
    DemandRunOptions,
    DemandRunSecurityOptions,
    ResourcesPolicy,
    WorkflowRunOptions,
    run_workflow,
)

result = run_workflow(
    "workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"]))),
        resources_policy=ResourcesPolicy(
            books={
                "report": BookResourcePolicy(
                    write=BookWritePolicy(
                        mode=BookWriteMode.APPEND,
                        header_policy=BookWriteHeaderPolicy.ONCE,
                    ),
                    budget=BookBudgetPolicy(max_sheets=8, max_total_cells=1_000_000),
                )
            }
        ),
    ),
)
```

demand 单跑同理：把 `resources_policy=` 挂到 `DemandRunOptions(...)`。

构造函数只接受 StrEnum（严格 in）；不要传裸字符串。

### 3) 替换旧 override / 旧公开类型

Before（不再允许）:

```python
from scalim.dsl.yaml_dsl import BookResourceOverride, BookWriteDefaultsOverride, BookBudgetOverride

BookResourceOverride(
    write_defaults=BookWriteDefaultsOverride(mode="append"),
    budget=BookBudgetOverride(max_sheets=1, max_total_cells=1000),
)
```

After: 用第 2 步的 `ResourcesPolicy`；`BookResourceOverride` 仅保留 path / export / `allow_formulas` 等 IO identity overlay。

### 4) 下游仓库快速扫描

```bash
rg -n "write_defaults:|xlsx_memory:[\\s\\S]*budget:|BookWriteDefaultsOverride|BookBudgetOverride" -S .
```

对每一处:
1. 删除 YAML 字段
2. 把策略搬到对应 `run` / `run_workflow` 的 `resources_policy`
3. 再跑你的 validate / 回归用例

仓库内建议至少跑:

```bash
just gen-yaml-dsl-schema
just gen-agent-skill
just gen-docs
just llmanspec-check
just qa
```
