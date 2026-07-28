# 2026-07-13: unified-xlsx-book-kind

> **NOTE（后续 BREAKING）**：`BookBudgetPolicy` 已在 `2026-07-28-remove-book-budget-policy` 移除；勿再抄 After 中的 budget 示例。

> **状态（2026-07-20）**：本批次引入的 deprecated 别名过渡期已结束；`xlsx_file` / `xlsx_memory` **已硬删**。当前唯一 authoring SSOT 与迁移表见 `2026-07-20-remove-deprecated-xlsx-file-memory-kinds.md`。下文保留本批次落地时的过渡描述。

## 变更摘要

本批次把 YAML book identity 收敛为统一分支 `resources.books.<id>.xlsx`，用**可选 `path`**区分落盘与内存总线；旧 `xlsx_file` / `xlsx_memory` 在本批次时尚可解析并发出 **warning 级 deprecated**（不因 deprecated 单独 fail）。

| YAML | 语义 |
|---|---|
| `xlsx: {}` | 内存总线（原无 export 的 `xlsx_memory`） |
| `xlsx: {path: ./out}` | 版本化落盘（原 `xlsx_file`） |
| `xlsx_file` / `xlsx_memory` | deprecated 别名（过渡期） |

硬约束（不变）：

- YAML **只**声明 identity / 结构；**禁止**在 `xlsx` 下写 `export_xlsx` / `write_defaults` / `budget`
- write 仍在 Python：`ResourcesPolicy` / `BookWritePolicy`（`WorkflowRunOptions.resources_policy`）
- book cell/sheet **budget 已移除**（见 `2026-07-28-remove-book-budget-policy.md`）；勿再配置 `BookBudgetPolicy`
- 本批次 **不**硬删旧 kind；硬删属后续 BREAKING follow-up

对应 llmanspec change: `llmanspec/changes/archive/2026-07-13-c20-add-unified-xlsx-book-kind/`

上游边界: `references/upgrades/2026-07-12-book-write-policy-python-ssot.md`

## Migration Checklist

### 1) 落盘 book：`xlsx_file` → `xlsx.path`

Before:

```yaml
resources:
  books:
    report:
      xlsx_file:
        path: ./out
```

After:

```yaml
resources:
  books:
    report:
      xlsx:
        path: ./out
```

### 2) 内存总线：`xlsx_memory: {}` → `xlsx: {}`

Before:

```yaml
resources:
  books:
    scratch:
      xlsx_memory: {}
```

After:

```yaml
resources:
  books:
    scratch:
      xlsx: {}
```

### 3) 旧 `xlsx_memory.export_xlsx` → `xlsx.path`

Before（仍可跑，但有 deprecated warning）:

```yaml
resources:
  books:
    report:
      xlsx_memory:
        export_xlsx: {path: ./out}
```

After:

```yaml
resources:
  books:
    report:
      xlsx:
        path: ./out
```

### 4) 不要在新分支写 `export_xlsx`

```yaml
# 错误 — fail-fast（不是 warning）
resources:
  books:
    report:
      xlsx:
        export_xlsx: {path: ./out}
```

### 5) write 仍在 Python（budget 勿再配）

> 下文仅展示仍有效的 `BookWritePolicy`。历史示例中的 `budget=BookBudgetPolicy(...)` 已删除。

```python
from scalim.dsl.yaml_dsl import (
    BookResourcePolicy,
    BookWriteMode,
    BookWritePolicy,
    ResourcesPolicy,
    WorkflowRunOptions,
)

WorkflowRunOptions(
    resources_policy=ResourcesPolicy(
        books={
            "report": BookResourcePolicy(
                write=BookWritePolicy(mode=BookWriteMode.SHEET),
            )
        }
    )
)
```

## Deprecated warning

- 级别：**warning**（`DeprecationWarning` + validate `ValidationIssue` warning）
- 仅因使用旧 kind **不会** error
- 稳定文案含迁移片段：`xlsx: {path: ...}` / `xlsx: {}`

## 明确不做

- 不合并 workbook/sheetbook 后端实现文件
- 不提供 YAML 开关关闭 deprecated warning
- 不在本批次删除 `xlsx_file` / `xlsx_memory` 解析路径
