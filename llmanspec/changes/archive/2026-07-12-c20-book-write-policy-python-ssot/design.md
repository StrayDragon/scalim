# Design: book-write-policy-python-ssot

## Goal

把 book 写入策略与内存 budget 从 YAML authoring 迁到 Python runtime policy，同时保留 YAML 的资源 identity 声明，并保证**不传 policy 时开箱行为与今日缺省一致**。

## Layering (target)

| Layer | Surface | Contents |
| --- | --- | --- |
| 1 | YAML `resources.books/files` | id、oneOf variant、`path` / `export_xlsx.path`、（暂留）`allow_formulas`/`encoding` |
| 2 | Python policy SSOT | `write_defaults` 五字段 + `budget` |
| 3 | YAML `outputs[*]` | 内容编排 + `to` 绑定；`write` 仅 output-local header |
| 4 | Python extras | meta/audit 等（已有方向） |

**Precedence (effective policy):**

```text
builtin_defaults  ◀  WorkflowRunOptions/DemandRunOptions 上的显式 ResourcesPolicy/BookWritePolicy
```

YAML 不再参与 write/budget 合并。迁移期内若 YAML 仍出现这些字段 → **parse/validate fail-fast**（不做 silent ignore）。

## API sketch (normative intent; names can adjust in impl)

```python
@dataclass(frozen=True)
class BookWritePolicy:
    mode: str = "sheet"  # sheet|append — 实现时用 StrEnum SSOT
    align_by: str = "field_id"
    header_policy: str = "once"
    on_mismatch: str = "error"
    on_conflict: str = "error"

@dataclass(frozen=True)
class BookBudgetPolicy:
    max_sheets: Optional[int] = None  # None = unlimited
    max_total_cells: Optional[int] = None

@dataclass(frozen=True)
class BookResourcePolicy:
    write: BookWritePolicy = BookWritePolicy()
    budget: BookBudgetPolicy = BookBudgetPolicy()

@dataclass(frozen=True)
class ResourcesPolicy:
    books: Mapping[str, BookResourcePolicy] = ...
```

挂载点（择一在实现 tasks 收敛，优先 workflow）：

- `WorkflowRunOptions.resources_policy: Optional[ResourcesPolicy] = None`
- demand 单跑若仍需要 book policy，经 `DemandRunOptions` 等价字段或明确「仅 workflow 支持」并在 docs 写清

`RunOverrides.resources`：

- **保留** path / export path 等 IO 声明 overlay（与 identity 相关）
- **移除或 reject** 对 `write_defaults`/`budget` 的 overlay 补丁（避免双路径）；若需短暂兼容，仅在一个 minor 内接受并 warn，然后删除

## Schema / validation

- `yaml-dsl-books-resources` schema：books 对象 **additionalProperties / properties** 不再包含 `write_defaults`；`xlsx_memory` 不再包含 `budget`
- validator：若旧字段出现，错误信息 MUST 含迁移提示（指向 Python policy 类型与文档锚点）
- 生成：改 SSOT models → `just gen-yaml-dsl-schema`（或仓库约定入口）→ 禁止手改 `*.gen.json`

## Migration

1. 文档示例去掉 YAML `write_defaults`/`budget`
2. 测试夹具改为 Python policy
3. skill / capability-matrix / workflow.md 同步
4. `notplan/c0-roadmap-yaml-dsl-oneof-checklist` 标 DONE/删除（与本 change 无关但同批次清理可选）

## Risks

| Risk | Mitigation |
| --- | --- |
| append 场景失去「纯 YAML 自描述」 | 接受；demo 用短 Python runner；编排仍可读 |
| 命名/挂载点争论拖慢实现 | design 允许 rename，tasks 先落地行为再 polish 导出 |
| 与 `allow-formulas-safe-default` 交错 | 本 change 不碰默认值；公式字段仍可 YAML |

## Downstream

`workflow-shared-book-memory` **depends_on** 本 change：用 Python `BookBudgetPolicy` 与释放策略，而不是 YAML budget。
