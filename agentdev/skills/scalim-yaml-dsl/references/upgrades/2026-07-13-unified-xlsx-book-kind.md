# 2026-07-13: unified-xlsx-book-kind

## 变更摘要

本批次把 YAML book identity 收敛为统一分支 `resources.books.<id>.xlsx`，用**可选 `path`**区分落盘与内存总线；旧 `xlsx_file` / `xlsx_memory` 仍可解析，但会发出 **warning 级 deprecated**（不因 deprecated 单独 fail）。

| YAML | 语义 |
|---|---|
| `xlsx: {}` | 内存总线（原无 export 的 `xlsx_memory`） |
| `xlsx: {path: ./out}` | 版本化落盘（原 `xlsx_file`） |
| `xlsx_file` / `xlsx_memory` | deprecated 别名（过渡期） |

硬约束（不变）：

- YAML **只**声明 identity / 结构；**禁止**在 `xlsx` 下写 `export_xlsx` / `write_defaults` / `budget`
- write / budget 仍在 Python：`ResourcesPolicy` / `BookWritePolicy` / `BookBudgetPolicy`（`WorkflowRunOptions.resources_policy`）
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

### 5) write / budget 仍在 Python

```python
from scalim.dsl.yaml_dsl import (
    BookBudgetPolicy,
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
                budget=BookBudgetPolicy(max_sheets=16, max_total_cells=2_000_000),
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
