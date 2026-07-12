# Design: workflow-shared-book-memory

## Dependency

- `book-write-policy-python-ssot` **已归档**；P1 使用其 `BookBudgetPolicy` / `ResourcesPolicy` 挂载点。
- 本 change 无开放设计选项；含糊项已迁出 futures。

## Current model (keep)

```text
demand run → managed ROWS artifact
    → write node (controller single-writer) materialize → plan segments
    → (optional) book_sheet_rows reads plan
    → success: openpyxl write_only commit → staging → publish
    → failure: discard (no partial final xlsx)
```

## Release strategy（P0）

### Consumer closure（规范）

对 managed artifact `A`（producer run / output 绑定）：

| 计入消费者 | 不计入 |
| --- | --- |
| 尚未完成的 write node，其输入解析到 `A` | workflow 结束后用户代码持有的引用 |
| 尚未完成的 node，其 `book_sheet_rows`（或等价）依赖该 producer 的 book plan 可见性，且该可见性以 `A` 的写入为前置 | `CaptureRows` / 非 workflow-managed 捕获 |

「无剩余消费者」= 上表左列集合为空。

### Actions

1. Write node 成功 apply `A` → plan 后，若 `A` 无剩余消费者 → discard demand 侧 `A`。
2. `commit_all` 成功或 `discard_all` 完成后 → 清空/丢弃各 book plan 的 segment 行数据。
3. Diagnostics：在释放点写结构化诊断（原因枚举：`no_remaining_consumers` | `commit` | `discard`），走既有 diagnostics/log，不新增 YAML/公开 Event 类型。

### Evidence

- pytest：可控多 write / 单 write 场景断言 discard 被调用或 artifact 随后不可见
- 可选：`.tmp/` 下弱引用/对象计数探针（不提交）

## Budget（P1）

| Kind | 本 change |
| --- | --- |
| `xlsx_memory` | MUST 从 effective `BookBudgetPolicy` 强制；omit = unlimited；超限 fail-fast |
| `xlsx_file` | MUST NOT 套用同一 cell/sheet budget（保持 unlimited） |

YAML budget authoring：已由 c20 拒绝；本 change 只补回归测与文档残留。

上游 compile 已对 `xlsx_memory` 注入 `book_options["budget"]`；实现以 **对拍 + 缺口修复** 为主，避免重复造 API。

## Out of scope（→ futures）

见 `llmanspec/futures/xlsx-file-numeric-type-loss/future.md` Deferred — shared-book 后续：

- spill / 分段 commit
- sheet seal
- 边写 openpyxl + profile
- `xlsx_file` cell budget
- demand 宽表 ColumnExcelSink streaming（notplan reframe）

## Source links

- futures R2: `llmanspec/futures/xlsx-file-numeric-type-loss/future.md`
- notplan (reframe later): `llmanspec/notplan/c1-streaming-xlsx-output/`
- notplan carrier: `llmanspec/notplan/c1-runtime-performance-profiles/`
- upstream archive: `llmanspec/changes/archive/2026-07-12-c20-book-write-policy-python-ssot/`
