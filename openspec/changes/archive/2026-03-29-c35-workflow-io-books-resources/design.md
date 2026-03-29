## Context

当前仓库的 workflow 输出体系由三块拼接而成：

1) demand outputs（`outputs[*].container`）负责写出 workbook/csv 文件；  
2) workflow resources（`workflow.resources.workbooks/csvs/sheetbooks`）声明共享输出容器；  
3) workflow writes（`workflow.runs[*].writes`）把某个 demand output 再写入共享资源（并且 **writes 目前只支持消费 CSV outputs**）。

为了让 writes 能消费“不落盘”的中间态，系统又引入了 pathless CSV 输出：
`outputs[*].container.type: csv` + `path: ""` 触发 workflow-managed in-memory CSV（实现细节泄露为 DSL 主路径）。

该组合在实践中带来明显痛点：

- 无 LSP 的前提下，`writes` 强迫用户在 demand/workflow 两份 YAML 之间来回对照（output id、sheet 名、冲突策略等），导致 authoring 复杂且易错。
- pathless CSV 使单 demand 失去“可独立运行”直觉：同一份 demand YAML 在 workflow 内可用、standalone 却 fail-fast（或需要额外 override）。
- workbook/sheetbook 概念割裂：两者在用户侧都是“一个 Excel book”，但 DSL 把它们拆成不同资源类型，并叠加 CSV-only writes 约束，使 IO 模型难以扩展（例如将资源同时用于 input/output、以及让编排只做 IO 绑定）。

本变更的设计方向参照 Dagster 的 IO 分层：**计算定义输出契约；编排只绑定 IO 资源**（类似 IOManager 的 handle_output/load_input），把中间态与写入节点作为内部实现细节，而不是 YAML authoring surface 的主路径。

## Goals / Non-Goals

**Goals:**

- 统一资源模型：在 demand 与 workflow 中引入一致的 `resources.books`，把 workbook/sheetbook 的用户侧概念收敛为单一“book”资源。
- 统一 IO 绑定写法：把 outputs→book/sheet 的绑定视为输出契约的一部分（可默认），并让 workflow YAML 多数情况下 **不需要出现 output name**。
- 保留确定性与可验证的写入行为：支持“多个 runs 同一 sheet 自动追加”，并保持写入顺序可复现且独立于并发完成时序。
- 移除 pathless CSV hack：不再允许 `container.path: ""` 作为触发条件；workflow-managed 中间态仍可存在，但必须成为实现细节（自动选择内存/临时文件）。
- Python overrides 收敛为 IO-only：`run()` / `run_workflow()` 能覆盖 `resources.books` 的路径/预算/导出配置（以及可选的 outputs 默认 book），而 workflow YAML 不能改 outputs 定义层（fields/aggregate/where）。
- 产出完整的 SSOT：OpenSpec specs + docs + skills 指南与可验证的迁移/测试任务。

**Non-Goals:**

- 不在本变更中引入“从磁盘读取 xlsx 作为 input book”的完整能力（未来可扩展；本变更先保证 `xlsx_memory` 的 workflow 内读取能力一致化）。
- 不在本变更中引入 YAML LSP（但 schema/结构必须为 LSP 友好）。
- 不在本变更中解决输出路径 allowlist/沙箱（属于 `c10-security-hardening-output-config` 的治理范围；本变更只保证接口设计可与其集成且不回退安全边界）。

## Decisions

### Decision 1: 使用 `resources` 作为唯一资源入口（拒绝 `bind:`）

- **选择**：沿用并扩展 `resources` 作为唯一入口：`resources.books`（demand + workflow）。
- **理由**：`resources` 既符合直觉又与 Dagster “resources / IO manager” 的 mental model 接近；比 `bind/mount/attach` 更少实现术语色彩。
- **替代**：`io:`（更强调 IO）与 `connections:`（更强调外部系统连接）。本变更优先保持最少概念与迁移成本，故保留 `resources`。

### Decision 2: `books` 统一 workbook/sheetbook，使用 `kind` 区分实现

定义：

- `resources.books.<id>`：统一表示“一个 Excel book”资源。
- `books.<id>.kind`：区分实现策略（建议扁平枚举，易写易校验）：
  - `xlsx_file`：文件输出（等价于当前 workflow `workbooks` + 原子替换 + 写锁）
  - `xlsx_memory`：内存 book（等价于当前 workflow `sheetbooks` + budget + 可选 export_xlsx）

选择 `kind`（而非 `backend`）的原因：

- 避免与执行“backend/engine 模式”概念冲突；
- 与现有 repo 中其它“kind/category”用法一致（例如资源类型、事件类型等）。

### Decision 3: 输出契约采用 `outputs_defaults.to.book` + `outputs[*].to`，sheet 默认等于 output.name

主路径写法（demand 可独立运行）：

```yaml
resources:
  books:
    report: {kind: xlsx_file, path: ./out/report.xlsx, write_lock: true}

outputs_defaults:
  to: {book: report}

outputs:
  - name: metrics
    fields: [a, b, c]     # sheet 默认 "metrics"
  - name: summary
    aggregate: {...}      # sheet 默认 "summary"
```

默认规则：

- 若 `outputs[*].to.sheet` 缺省：`sheet = outputs[*].name`
- 若默认 sheet 名不满足 Excel 约束（长度/非法字符等）：**fail-fast**，要求显式提供 `to.sheet`
- 若 `outputs[*].to` 缺省：从 `outputs_defaults.to` 继承（仅继承 `book`；sheet 不继承）
- 若两者都缺省但该 output 需要写出：fail-fast 并给出可复制的迁移提示

该决策的关键收益：workflow YAML 不再需要维护 output→sheet 的映射；用户只需要在 demand 中定义稳定 output 名（输出契约），即可得到稳定 sheet 名。

### Decision 3b: `.xlsx` 输出写法收敛到 books（移除 `container.type: workbook`）

为满足“尽可能单一写法/一致理解”的指导思想,本变更将 `.xlsx` 输出的用户侧写法收敛到:

- `resources.books` + outputs→book 绑定(`outputs_defaults.to.book` / `outputs[*].to`)

并破坏性移除:

- `outputs[*].container.type: workbook`（以及 `container.sheet/allow_formulas/write_lock/path` 等 workbook-only authoring surface）

动态路径注入也随之收敛:

- 由 `outputs[*].container.path: {$init_var: ...}` 迁移为 `resources.books.*.path` / `export_xlsx.path`

说明:

- `outputs[*].container` 不再作为 `.xlsx` 输出的稳定 authoring surface；若仍需 CSV 文件输出,仅保留 `type: csv` + **非空 path** 的最小子集（支持静态字符串或 `{$init_var: ...}` 指令节点；未来可再统一到 `outputs[*].to` union,见 Open Questions）。

### Decision 4: 追加写入是主流能力：`books.*.write_defaults.mode=append`

为满足“多个 runs 同一 sheet 自动追加”的主流需求，定义统一的写入策略（与当前 `*_append` 语义对齐）：

- `write_defaults.mode`: `append|sheet`（分别对应当前 `append_sheet` 与 `write_sheet` 两类节点语义）
- `write_defaults.align_by`: `field_id|header`
- `write_defaults.header_policy`: `once|always|never`
- `write_defaults.on_mismatch`: `error|warn|skip`
- `write_defaults.on_conflict`: `error|overwrite|skip`（仅对 `mode=sheet` 生效）

默认建议：

- `mode=append`
- `align_by=field_id`
- `header_policy=once`
- `on_mismatch=error`

并允许 `outputs[*].write` 覆盖（覆盖只限写入策略，不触及字段/aggregate 定义层）。

### Decision 5: workflow 移除 `runs[*].writes`，改为“从输出绑定推导内部写入节点”

workflow YAML 的职责收敛为：

- DAG 与上下文：`runs/depends_on/init_vars/main_rows_from/ctx`
- 运行治理：`max_concurrency/failure_policy/cache_pool`
- 共享资源：`workflow.resources.books`

编译阶段：

- 读取每个 run 引用的 demand YAML（compile-on-ready 仍适用）
- 从 demand 的 `outputs_defaults` + `outputs[*].to/write` 推导需要的写入节点
- 为同一 book 资源生成确定性的串行化依赖链（等价于当前 `last_write_node_id_by_resource`）
- 对 `xlsx_memory`（原 sheetbook）保持“下游读取可见性”注入（等价于当前 sheetbook write node deps 注入）

这保持了现有系统的执行模型与可观测事件，但移除了用户手写映射层。

### Decision 6: workflow-managed 中间态变为实现细节（删除 pathless CSV authoring surface）

原则：

- DSL 不再出现“空路径触发 in-memory CSV”的入口；
- 写入节点的输入可以来自文件路径、内存 CSV、或其它中间态，但这些由实现自动选择；
- standalone demand 永远可以运行（只要资源绑定存在），不会因为“是否被 workflow 引用”而改变合法性。

实现可选路径（留给实现阶段择优）：

- 继续复用 `InMemoryCsv`（仅作为内部 artifact，不再由 YAML 显式触发）
- 或升级为 `InMemoryRows`（typed rows），再在需要时转换为 CSV/列存

本变更只规定“外部 authoring surface 不再暴露 pathless CSV”。

### Decision 7: 资源路径解析基准统一为“声明该资源的 YAML 文件所在目录”

为减少“同一系统不同文件不同基准”的惊讶，定义：

- `demand.resources.books.*.path` 相对路径以 demand YAML 所在目录为基准
- `workflow.resources.books.*.path` 相对路径以 workflow YAML 所在目录为基准

说明：这与当前 workflow 资源解析一致，但与当前 `outputs.*.container.path` 的 CWD 语义不同；由于本变更本身已是大幅 breaking change，选择在此处一次性收敛到更直觉的规则（同时降低下游集成的搬运成本）。

### Decision 8: Overrides 分层与边界（workflow 不改输出定义；Python 可做 IO-only 覆盖）

分层（合并优先级从低到高）：

1) demand YAML 自带 `resources.books`（保证可独立运行）
2) workflow YAML 的 `resources.books` 覆盖同名资源（集中管理共享路径/预算）
3) Python overrides 作为最终覆盖层（运行时按环境/用户/批次注入路径与预算）

边界：

- workflow YAML **不得**新增/删除 outputs，也不得修改 fields/aggregate/where 等“输出定义层”
- workflow YAML **仅允许**做 IO 绑定与资源治理（路径/预算/export/写入策略）
- Python overrides 可覆盖 IO 绑定（以及保留高级 escape hatch），但必须在 API 文档中明确“trusted only”

## Risks / Trade-offs

- **[BREAKING DSL]** 需要一次性升级现有 demand/workflow YAML。→ 缓解：提供 `scalim-cli yaml-dsl upgrade` 的专用升级器（包含可复制的迁移提示与校验回归），并更新 docs/skills/examples。
- **[实现复杂度]** workflow 编译需要加载 demand 并推导写入节点，且必须保持确定性与可观测事件语义一致。→ 缓解：保留现有内部 node 模型（write_sheet/append_sheet），仅改变“生成这些节点的 authoring surface”；新增确定性回归测试（并发执行多次结果一致）。
- **[安全/治理]** 输出路径仍是强权限面（任意路径写入）。→ 缓解：在设计与实现中显式预留 `allowed_output_roots`/policy 接口，并在文档中明确 trust model；与 `c10-security-hardening-output-config` 对齐落地。
- **[YAML 解析 DoS]** 大 YAML/anchors 可能导致资源耗尽（属于平台化输入治理）。→ 缓解：文档化信任边界，并在后续安全治理变更中加入输入大小/复杂度护栏。
- **[资源语义扩展]** 未来若加入“xlsx 作为 input”将引入 zip/xml 解析类风险。→ 缓解：本变更仅统一资源模型与内存 book 读取；输入 xlsx 作为独立后续变更，并在规范中预留护栏（文件大小、行列上限等）。

## Migration Plan (high level)

1) 落地新 schema（`resources.books`、`outputs_defaults.to.book`、`outputs[*].to/write`；workflow resources.books）。
2) 实现运行时与 workflow 编译侧的写入节点推导；移除 `runs[*].writes` 与 pathless CSV 的支持。
3) 提供 upgrade 工具（静态升级 YAML），覆盖：
   - `workflow.resources.workbooks` → `workflow.resources.books.<id>.kind=xlsx_file`
   - `workflow.resources.sheetbooks` → `workflow.resources.books.<id>.kind=xlsx_memory`
   - `runs[*].writes` → 将目标 book/sheet 绑定移动到对应 demand outputs（默认 sheet=output.name；必要时写显式 `to.sheet`）
   - `outputs[*].container.type: csv + path: ""` → 删除并改为内部中间态（必要时将 output 改为写入 book）
   - `outputs[*].container.type: workbook` → 迁移为 `resources.books` + outputs→book 绑定
4) 更新 docs 与 skills，并通过 `just gen-docs` 与 `just qa` 做 drift gate。

## Open Questions

- 是否将剩余的 CSV 文件输出也统一为 `outputs[*].to`（例如 `to: {kind: csv_file, path: ...}`），从而彻底移除 `outputs[*].container` 概念？本变更先以 `.xlsx` 输出收敛为主路径,CSV 作为低频能力保守处理。
- `xlsx_file` 是否允许 workflow 内置 loader 读取（`book_sheet_rows`）？若支持，需要明确护栏与性能边界；若不支持，应在文档中明确“只支持读取 xlsx_memory”。
