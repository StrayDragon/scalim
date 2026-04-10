## Context

当前仓库的测试与质量门禁存在一个明显的“错配”：

- 我们已经有大量单测与回归用例，但质量信心很大程度上被 **覆盖率数字**牵引（甚至出现“coverage 达标但仍可能遗漏 bug”的情况，尤其是条件分支/异常路径/状态组合）。
- 同时我们计划推进大规模重构（例如 `yaml-dsl-compiler-frontend` 将 YAML DSL editor semantics 收敛为主框架编译前端 SSOT），这类重构最需要的是 **接口行为基线**（contract tests + golden fixtures），而不是更高的 statement coverage。

另外两个紧随其后的变更会直接受益于本变更的测试策略：

- `yaml-dsl-lsp-contract-tests`：将 `scalim-yaml-dsl-lsp` 的既有能力固化为协议级 contract tests，作为后续 refactor 的“红线”。
- `yaml-dsl-compiler-frontend`：静态编译前端产物（diagnostics/IR/plan/deps/effective view）天然适合做可序列化快照与 golden 对拍，需要一套明确的 fixture/snapshot 组织与更新流程。

关键约束与治理边界（本设计必须遵守）：

- `src/scalim/` 运行时仍需 Python 3.6 兼容；测试与工具链可在 Python 3.10+ 运行。
- 任何 `*.gen.*` 与 `BEGIN/END AUTOGEN:*` 注入区块禁止手改；生成物必须通过既有 `just gen-docs`/drift gate 管控。
- `tests-domain-suites` 约束仍成立：YAML 字符串引用的 callable 只能落在 `tests/fixtures/` 边界；`tests/support/` 仅用于 Python import 的测试工具，不得被 YAML 字符串引用。

本设计的目标是在不牺牲可维护性的前提下，把“测试信心来源”从覆盖率数字迁移到更贴近真实质量的 **行为契约** 上，并让覆盖率变成辅助的 guardrail（优先 branch coverage）。

## Goals / Non-Goals

**Goals:**

- 将质量门禁的主信心来源调整为：**行为契约（contract tests）+ golden fixtures + 关键边界的错误模型**，覆盖率只作为辅助指标。
- 在 `just qa`/CI 中 **收集并报告 branch coverage**（满足 delta spec 要求），并提供 **分阶段收敛**策略：
  - 先可见（report）；
  - 再局部设阈值（按目录/模块）；
  - 再逐步提高阈值（防止一次性把历史债务变成阻塞）。
- 给后续 refactor 提供“可执行基线”：
  - 对 YAML DSL LSP：协议级黑盒 contract tests（stdio server + JSON-RPC/LSP）。
  - 对 YAML DSL 编译前端：静态产物快照（schema_version + normalize）与回归样例集。
- 收敛测试分层与入口：明确 unit/contract/integration/notebooks/perf-regression 各自测什么、怎么跑、如何作为门禁的一部分。

**Non-Goals:**

- 不以“100% statement coverage”为目标（不再把它作为主 KPI）。
- 不在本变更内一次性重写/重组所有测试文件；优先做“规则与入口”的收敛，让后续变更渐进迁移。
- 不引入需要联网或重依赖的外部覆盖率平台/服务作为强依赖（CI 必须离线可跑）。

## Decisions

### D1) 明确测试分层：Unit / Contract / Integration / Notebooks / Perf

**决策：** 用“分层 + 入口 + 责任边界”来组织测试，而不是用覆盖率数字间接代表质量。

- **Unit tests（快速、局部）**
  - 关注：纯函数、数据结构、错误分类与边界条件。
  - 位置：继续放在现有 domain suites（例如 `tests/yaml_dsl/`、`tests/execution/`）。
- **Contract tests（行为契约、稳定基线）**
  - 关注：核心对外接口/边界的“黑盒行为”是否稳定。
  - 典型：CLI 子命令输出、LSP 协议行为、静态编译产物快照。
  - 基线策略：snapshot/golden（强约束 + 明确更新流程）。
  - 运行策略：默认进入 `pytest`（本地与 CI 一致），不额外引入 `contract` marker 作为“只在 CI 跑/只在本地跑”的分组门禁。
- **Integration tests（跨模块、真实链路）**
  - 关注：多模块协作（例如 runtime compile → execute → sink 输出），更偏“能跑通”与“错误模型一致性”。
  - 不要求高覆盖率，但要覆盖关键失败路径与可诊断性。
- **Notebooks regression（集成对拍/用户侧对拍）**
  - 关注：真实用户样例/端到端验证（更慢、更贵）。
  - 作为“回归兜底”，不是每次 PR 的唯一 gate。
- **Perf regression（基线）**
  - 关注：关键路径性能不回退（已有 bench 基线机制，继续复用）。

**替代方案：**

- A) 继续以 coverage 作为主要 gate：对重构回归不敏感，且会诱导“为了覆盖率写脆弱用例”。

结论：选择 D1。

### D2) 覆盖率策略：branch coverage 可见化优先，阈值分阶段收敛

**决策：** 覆盖率从“目标”降级为“护栏”，并将口径从 statement-only 扩展到 branch coverage：

- `just qa`/CI MUST 收集并报告 branch coverage（对应 `testing-behavior-contracts` delta spec）。
- 阈值策略采用分阶段推进：
  1) **Stage-0（可见化）**：在 QA 输出中稳定展示 branch coverage（不作为强 gate 或只做总阈值的宽松 gate）。
  2) **Stage-1（关键模块门槛）**：对高风险、频繁变更的目录/模块设置阈值（例如 YAML DSL 前端编译链路、执行计划构建等）。
  3) **Stage-2（逐步收紧）**：每次变更只能提高或维持阈值，避免覆盖率回退。

实现建议（后续 tasks 具体化）：

- 覆盖率阈值与采集口径直接写入仓内配置（`pyproject.toml`），不依赖修改 `justfile` 入口命令；这样 `just test`/`just qa` 的命令形态保持不变，但覆盖率口径按配置演进。
- 通过 `pytest-cov` 的 `--cov-branch`（或等价配置）采集 branch coverage，保证 CI 离线可跑。

**替代方案：**

- A) 直接把 branch coverage fail-under 设为 100：会把历史债务与偶然分支变成推进阻塞，不符合“行为契约优先”的主线。
- B) 完全取消 coverage：会失去一个低成本的“回退探测器”，且无法满足“branch coverage 可见化”的要求。

结论：选择 D2。

### D3) Golden fixtures / snapshots 的治理（SSOT + 更新流程）

**决策：** 对“可序列化且稳定”的产物建立 golden fixtures，并把它视为 contract tests 的核心机制之一。

治理规则（与现有 repo 约束对齐）：

- fixtures/snapshots 必须落在 `tests/fixtures/`（可被 git 管控、可 review），禁止写到 `.tmp/` 并提交。
- snapshots 必须包含显式 `schema_version`（允许未来演进而不把测试变成“偶然字典顺序对拍”）。
- 更新流程必须显式（例如 `UPDATE_GOLDEN=1`），默认不自动更新，避免“更新即通过”。

对后续两个变更的落地指引：

- `yaml-dsl-lsp-contract-tests`：
  - snapshots：normalize 后的 LSP responses（diagnostics/definition/hover/completion/code actions）。
  - harness：放在 `tests/support/`（不可被 YAML 字符串引用）。
- `yaml-dsl-compiler-frontend`：
  - snapshots：StaticCompilation 产物（diagnostics/plan/deps/effective view 的可序列化视图）。
  - 重点：range/path/ordering 的稳定化与 schema_version。

### D4) 门禁与文档/生成边界收敛（drift gates）

**决策：** 在测试策略升级的同时，保持既有“生成物与注入区块”的治理方式不被打穿：

- 禁止手改 `*.gen.*` 与 injected blocks；任何由测试/覆盖率引入的新增产物（如 coverage.json/xml）必须写入 `.tmp/` 或 CI artifacts 目录，并明确不提交。
- `just qa` 的 fail-fast 阶段仍优先执行静态治理门禁（例如 `check-tests-domain-suites`、`generated-artifacts-drift-check`、`openspec-check`）。

这样可以确保：

- 新增的 contract tests / snapshots 不会绕开既有治理；
- 大型重构（例如静态编译前端）不会导致文档/生成物漂移失控。

## Risks / Trade-offs

- [branch coverage 暴露大量历史缺口] → 采用分阶段阈值策略：先可见化，再对关键目录设门槛，最后逐步收紧。
- [golden snapshots 过脆/易被滥更] → 强制 normalize + schema_version + 显式更新入口（默认不更新），并要求行为变更必须在 review 中说明。
- [contract tests 易 flaky（异步/防抖/IO）] → 在测试中禁用 debounce、统一超时与等待点、失败时输出可诊断日志；必要时在 suite 级别复用 server 进程降低抖动。
- [CI 时长增加] → 用“最小场景覆盖矩阵”控制 contract tests 规模；慢用例用 marker 隔离；notebooks/perf 保持独立入口。

## Open Questions

- branch coverage 的初始阈值应如何定标（先跑一次基线，再设一个“不会阻塞历史但能防回退”的门槛）？
