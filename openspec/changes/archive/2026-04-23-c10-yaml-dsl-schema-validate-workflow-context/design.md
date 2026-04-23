## Context

当前 `scalim-cli yaml-dsl schema validate <demand.yaml>` 的校验模型是：

1) 使用 JSON Schema 做结构/类型校验（并执行 unknown-fields 收敛等）
2) 额外补充少量“schema 难以表达但运行时会 fail-late”的规则（例如：legacy 字段、retry 规则、outputs 绑定等）

其中 outputs 的资源绑定校验目前只覆盖 `to.book ↔ resources.books`，且在 standalone demand 入口仅能看到 demand 自身 `resources.books`，无法感知 workflow 级注入（`workflow.resources.books`）。这在 “workflow 统一声明资源 + 多 demand 复用” 的主流模式下会造成假阳性失败，迫使用户在每个 demand 内重复声明资源 stub，带来漂移风险。

此外，本变更希望将同一套“输出绑定 → 资源存在性”规则同时覆盖 `resources.files`（`to.file`) 与 `resources.books`（`to.book`) 两个资源面，避免校验口径不对称。

约束与原则：

- workflow YAML 不支持 imports expansion，本变更不改变该边界；`--workflow` 仅作为“上下文读取”，不展开 imports。
- CLI MUST 尽量复用 runtime core 的校验服务层（SSOT），避免在 CLI 内复制语义实现（见 `yaml-dsl-cli-validation`）。
- runtime 兼容 Python 3.6（本变更不引入新语法/新依赖）。

## Goals / Non-Goals

**Goals:**

- 为 demand 的 `yaml-dsl schema validate` 提供可选 workflow 上下文：`--workflow <workflow.yaml>`。
- 在提供 workflow 上下文时，让 demand 的 outputs→resources 绑定校验使用一致的“可见资源集合”口径：
  - visible books = `resources.books` ∪ `workflow.resources.books`
  - visible files = `resources.files` ∪ `workflow.resources.files`
- 绑定校验覆盖 books + files，并输出可定位、可行动的诊断信息（路径精确到 `outputs.<idx>.to.book/to.file`）。
- 同步将 `yaml-dsl validate`（demand 模式）引入同样的 `--workflow` 参数，保证 validate/schema-validate 行为一致（在“可见资源集合”层面）。

**Non-Goals:**

- 不引入“自动发现 workflow”或隐式上下文（避免不确定性）；只支持显式 `--workflow`。
- 不改变 workflow YAML 的校验入口边界（workflow 仍以 schema-only 校验为主；本变更不把 workflow validate 变成 schema validate）。
- 不在 demand YAML 中引入新的 DSL 指令（例如 `$from_workflow`），避免把运行时注入语义嵌入 authoring surface。
- 不引入 warning 降级策略；未知资源 id 仍为 error（fail-fast）。

## Decisions

### Decision 1: CLI 提供 `--workflow`，而非在 demand 引入 `$from_workflow` 指令

选择 `--workflow` 的原因：

- 上下文依赖是“校验入口策略”，而不是 demand 的 authoring surface；把它做成 CLI 参数更符合职责边界。
- `$from_workflow` 这类指令会弱化 fail-fast：同名 typo 很可能在 standalone 校验被静默放行，直到运行时才暴露（或在另一个入口才暴露）。
- workflow 的资源注入是运行时编排行为，保持其显式性更可控；CI/IDE 也能通过命令行标准化复现。

### Decision 2: 绑定校验统一覆盖 `to.book` 与 `to.file`

本变更引入对 files 的对称校验，避免出现：

- books 有资源存在性检查，但 files 缺失（导致 validate/schema-validate 与 runtime 之间出现 “fail-late 漏洞”）
- 校验逻辑碎片化（每个入口各做一半）

绑定校验的核心规则（对每个 `outputs[*]`）：

- 若绑定到 `to.file`：`to.file` MUST 为非空字符串，且在 visible `resources.files` 中存在。
- 若绑定到 `to.book`：`to.book` MUST 为非空字符串，且在 visible `resources.books` 中存在。
- 若两个都缺失：报错“缺少 destination”，提示显式设置 `to.file` 或 `to.book`。
- legacy `outputs[*].container`：跳过该条目的新模型绑定检查，并保持既有迁移提示（不在本变更扩大 legacy 行为面）。

### Decision 3: “可见资源集合”计算下沉到 core 服务层（CLI 仅做参数与 IO）

为了满足 `yaml-dsl-cli-validation` 的“校验逻辑 SSOT”要求：

- 在 core (`src/scalim/dsl/yaml_dsl/validation_service.py`) 中提供：
  - workflow resources id 的提取（books + files）
  - outputs→resources 绑定校验（books + files，带可定位 path）
- CLI (`packages/scalim-cli/...`) 只负责：
  - 解析 `--workflow` 参数
  - 读取 workflow 文件文本
  - 调用 core helper 得到 errors/warnings 并统一渲染

### Decision 4: `--workflow` 对 demand 有效，对 workflow schema validate 明确拒绝/忽略

`--workflow` 的语义是“给 demand 校验提供编排上下文”。因此：

- 当被校验的入口 YAML 本身为 workflow（例如用户显式 `--schema .../workflow.gen.json`）：`--workflow` 没有意义，应当 fail-fast 并给出可行动提示。
- 当入口 YAML 为 demand：`--workflow` 生效。

## Risks / Trade-offs

- **[新增 CLI 参数，用户习惯迁移]** → 在 docs/skill 中补充示例；并提供清晰的错误提示（当未知 book/file 时提示 `--workflow` 用法）。
- **[绑定校验覆盖范围扩大，可能让原本“错误但未被捕获”的配置在 CI 中失败]** → 这是预期的 fail-fast 收敛；通过变更说明与错误信息可行动性降低迁移成本。
- **[多入口一致性风险]**（schema validate / validate / workflow validate 口径漂移） → 将逻辑集中到 core service helper，并在 tests 中用同一套 fixture 覆盖多个入口。

## Migration Plan

1) 在 core service 层补齐 workflow resources 提取与 outputs→resources 绑定检查（books + files），并确保错误 path 口径稳定。
2) CLI：
   - `yaml-dsl schema validate` 增加 `--workflow`
   - `yaml-dsl validate`（demand 入口）增加 `--workflow`
3) 增加测试覆盖：
   - standalone demand + `--workflow`：允许引用 workflow 级 book/file id
   - 未提供 `--workflow`：保持原有 fail-fast 行为
   - 仍未知 id：继续 fail-fast（错误提示包含 `--workflow`）
4) 按需更新 docs/skill 命令示例，并通过既有生成入口刷新生成物（禁止手改 `.gen.` / injected blocks）。

## Open Questions

- `--workflow` 是否需要同时支持 `--path-alias`（workflow 内 run.demand path resolution）？
  - 当前目标仅是资源可见性（`workflow.resources.*`），无需解析 runs；因此 v1 不做。
  - 若未来希望“给 demand 自动提供允许的资源集合 + 校验引用链路”，可再引入扩展参数。
