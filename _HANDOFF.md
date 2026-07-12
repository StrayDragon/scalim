# Workflow 迭代方向 HANDOFF（临时）

> **临时进度追踪**：指导后续 agent/人类推进「YAML 编排瘦身 + Python policy SSOT + 共享 book 内存」方向。  
> 归档两条主 change 并合并进 specs 后，可删除或迁入 `docs/doc/dev/` 常驻页。  
> 会话 SSOT 日期：2026-07-12。

## 方向一句话

- **YAML DSL**：只承担编排与资源 identity（runs / 依赖 / `resources.*.id+variant+path` / `outputs.to` / 内容字段）。
- **Python**：承担 `write_defaults`、`budget` 及同类调参（开箱 builtin defaults；显式 policy 覆盖）。
- **共享 book**：多节点写入仍合法；openpyxl 仅最终 commit；性能问题在 plan 全量物化，不在并发写 xlsx。

## Active changes（依赖）

```mermaid
flowchart TD
  c20["c20-book-write-policy-python-ssot"]
  c30["c30-workflow-shared-book-memory"]
  c30 -->|depends_on| c20
```

| Change | 角色 | 状态 | 校验 |
| --- | --- | --- | --- |
| `c20-book-write-policy-python-ssot` | 边界：write_defaults + budget → Python SSOT；YAML reject | **proposed / ready to apply** | `llman sdd validate c20-book-write-policy-python-ssot --strict --no-interactive --stage spec` |
| `c30-workflow-shared-book-memory` | 性能：P0 释放 + P1 Python budget 接线 | **proposed；depends on c20** | `llman sdd validate c30-workflow-shared-book-memory --strict --no-interactive --stage spec` |

推进命令：

```bash
llman sdd show c20-book-write-policy-python-ssot
llman sdd graph c20-book-write-policy-python-ssot --depth 2
# 实现时用 llman-sdd-apply，先 c20 再 c30
```

## 已拍板决策

| # | 决策 |
| --- | --- |
| 1 | `resources.books/files` 的 **id / variant / path**（及 `export_xlsx.path`）**留 YAML** |
| 2 | **`write_defaults` → Python SSOT**（选项①，不是 YAML+overlay 双轨） |
| 3 | **`budget` → Python SSOT** |
| 4 | **`allow_formulas` / `encoding` 暂保持 YAML 可写**（一般不动态改） |
| 5 | 开箱：不传 policy = 今日缺省（`mode=sheet`, `on_conflict=error`, …；budget unlimited） |
| 6 | 两线都落 formal change；c30 depends_on c20 |

## 目标态例子

### YAML（瘦）

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

### Python（SSOT；API 名以 c20 design 为准）

```python
result = run_workflow(
    "workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(...),
        # resources_policy=ResourcesPolicy(books={
        #   "report": BookResourcePolicy(
        #       write=BookWritePolicy(mode="append", header_policy="once"),
        #       budget=BookBudgetPolicy(max_sheets=8, max_total_cells=1_000_000),
        #   )
        # }),
    ),
)
```

## 与其它 active changes 的协调

**结论：没有任何 active change 被 c20/c30 整份取代。** 多数正交；下表仅列交叉项。

| Change | 关系 | 建议 |
| --- | --- | --- |
| `c0-output-write-path-allowlist` | 同碰 `books-resources` / shared-output；主题是 path 白名单（Python 入口） | **互补**；合 delta 时注意别互相覆盖。方向与「调参进 Python」一致 |
| `c1-allow-formulas-safe-default` | 同碰 books 的 `allow_formulas` | **不取代**；c20 **暂留该字段在 YAML**。c1 只改默认 true→false。apply 时先保证字段仍在 YAML，再改默认值 |
| `c5-extract-openpyxl-shared-helpers` | 同改 `resources_workbook/sheetbook` | **有利前置（soft）**；先做可减 c30 重复，非硬 `depends_on` |
| `c5-workflow-temp-file-permissions` | staging/publish 邻近 | **正交加固**；可与 c30 并行，注意同一文件合并 |
| 其余 c0/c1/c10（timestamp、sleep fixtures、trusted-mode、compute-dos、preloaded-cache、adaptive-locks） | 无交叉 | 照旧推进 |

各交叉 proposal 内已加「与 c20/c30 关系」小节。

## 相关工件（合并 / 移除意向）

| 工件 | 意向 |
| --- | --- |
| `governance-mainline-principles` / `yaml-dsl-runtime-policy-boundary` | KEEP；被 c20 扩展 |
| `yaml-dsl-write-policy-and-output-extras` | REWRITE（c20）：Python write SSOT |
| `yaml-dsl-books-resources` | KEEP 骨架；削 write_defaults/budget（c20） |
| `workflow-shared-output-containers` | KEEP 生命周期；策略来源改 Python（c20）；释放/budget（c30） |
| `notplan/c0-roadmap-yaml-dsl-oneof-checklist` | REMOVE/stale（oneOf 已落地） |
| `notplan/c1-streaming-xlsx-output` | REFRAME：禁止 YAML streaming knobs；另案 Python/profile（**非**被 c30 直接实现） |
| `notplan/c1-runtime-performance-profiles` | KEEP 为后续载体 |
| `futures/.../R2` 峰值内存 | c30 部分消化 |

## 建议推进顺序

1. **Apply `c20`**（schema reject + policy API + 测试/文档迁移）
2. **Apply `c30` P0/P1**（释放 + budget 接线）
3. （可选）reframe streaming notplan / 引入 performance profiles
4. 归档后刷新本 HANDOFF 或删除

## 不要做的事

- 不要把 flush/streaming/budget/write_defaults 重新加回 YAML 主线
- 不要默认「边写边 openpyxl」破坏原子 discard（除非独立 change + 显式 profile）
- 不要手改 `*.gen.json` schema

## 指针

- Changes: `llmanspec/changes/c20-book-write-policy-python-ssot/`、`llmanspec/changes/c30-workflow-shared-book-memory/`
- 上位原则: `llmanspec/specs/governance-mainline-principles/spec.toon`
- Review checklist: `docs/doc/yaml-dsl/review-checklist.md`
- AGENTS 短规则: `AGENTS.md`（YAML authoring vs Python policy）
