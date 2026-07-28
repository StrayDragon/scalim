# 2026-07-28: remove-book-budget-policy

## 变更摘要

BREAKING：移除 pathless/pathful book 的进程内 cell/sheet 预算护栏。

| 面 | 移除项 |
|---|---|
| Python | `BookBudgetPolicy`；`BookResourcePolicy.budget`；`ResourcesPolicy.budget_policy_for` |
| 内部 | `BookBudgetConfig` / `BookConfig.budget`；sheetbook `budget_max_*` 与运行期校验 |
| YAML / RunOverrides | 残留 `budget` 仍 **fail-fast**，提示改为「已移除；请删除；内存风险交宿主」——**不再**指向 `BookBudgetPolicy` |

**保留**：`BookWritePolicy`（写入策略 Python SSOT）；workflow `cache_pool` budget（另一套能力）。

对应 change：`llmanspec/changes/archive/2026-07-28-c0-remove-book-budget-policy/`

历史上下文：`2026-07-12-book-write-policy-python-ssot.md`（当时把 budget 迁到 Python；本批次删除该能力）。

## Migration Checklist

### 1) Python：删除 BookBudgetPolicy

Before：

```python
from scalim.dsl.yaml_dsl import BookBudgetPolicy, BookResourcePolicy, BookWritePolicy, ResourcesPolicy

ResourcesPolicy(
    books={
        "report": BookResourcePolicy(
            write=BookWritePolicy(),
            budget=BookBudgetPolicy(max_sheets=16, max_total_cells=2_000_000),
        )
    }
)
```

After：

```python
from scalim.dsl.yaml_dsl import BookResourcePolicy, BookWritePolicy, ResourcesPolicy

ResourcesPolicy(
    books={
        "report": BookResourcePolicy(write=BookWritePolicy()),
    }
)
```

### 2) YAML：删除残留 budget 字段

`resources.books.*.budget` / `xlsx.budget` / 旧 `xlsx_memory.budget` 出现即 fail-fast。删除该字段即可；内存风险改由宿主 cgroup / OOM killer / 作业配额兜底。

### 3) RunOverrides

`RunOverrides.resources` 补丁中的 `budget` 同样 fail-fast（能力已移除，不是迁到别处）。

## 常见报错与修复

- `budget was removed; delete this field... host resource limits`
  - 从 YAML / override 删除 `budget`
- `TypeError` / `ImportError` 涉及 `BookBudgetPolicy` 或 `budget=`
  - 从 Python `ResourcesPolicy` 构造中删除 budget 相关代码
