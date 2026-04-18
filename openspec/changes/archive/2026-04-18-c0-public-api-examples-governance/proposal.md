## Why

当前仓库的 `scalim.*` 公共 API/能力演进速度，已经开始超过 `notebooks/marimo/**` 示例与 `agentdev/skills/**` 的维护节奏：当维护者调整 Tier1 curated entrypoints、`__all__` 导出面或 YAML DSL 相关运行期契约时，示例与技能很容易“看起来还能跑”，但实际用法已经落后且缺少可回归的覆盖绑定，导致下游接手成本高、漂移难发现。

我们需要把“public API 清单 → 可运行示例 → skills 可复制样例代码 → gates”串成一条确定性机制，让任何 public surface 变更都被迫同步更新对应示例与技能参考。

## What Changes

- 建立一个新的 Codex skill：`agentdev/skills/scalim-public-api/`，用于维护 Scalim public API 的“推荐导入 + 可运行最小闭环样例代码 + 常用 gate/生成入口”。
- 为 `scalim-public-api` skill 引入确定性生成与校验机制（仅生成 `references/**/*.gen.*` 与 `references/generated/**`），并纳入：
  - `just gen`（生成入口）
  - `just qa`（drift/gate 入口）
- 增加一个静态治理 gate：强制 Tier1 curated entrypoints 与示例覆盖保持一致（fail-fast 输出缺失/新增差异），并把该 gate 作为 `just qa` 的 pytest 之前阶段执行：
  - Tier1 SSOT：`src/scalim/**/__init__.py` 中的 `# pragma: scalim-public-api tier1:...`
  - 示例 SSOT：`notebooks/marimo/example_public_api_suite/**` 的章节集合与 `tests/public_api/**`
- 补齐/重组 public API 覆盖套件，使其覆盖当前 Tier1 入口集合（例如补齐 `scalim.events.type_groups`、`scalim.sinks.pandas` 等缺口），并保持“章节 = 教学入口 + headless SSOT”一体化结构不变。
- 顺带刷新 `notebooks/marimo/**` 的 marimo 元信息到当前依赖锁定版本（避免 notebook/导出链路对 marimo 版本产生隐式耦合与漂移）。

## Capabilities

### New Capabilities
- `public-api-agent-skill`: 新增并治理一个面向 public API 的 Codex skill（包含确定性生成的参考产物与可运行样例代码索引），并把其生成/校验纳入 `just gen`/`just qa`。

### Modified Capabilities
- `marimo-example-public-api-suite`: public API suite MUST 与 public API manifest 对齐，并具备可回归的 drift gate（覆盖集合缺失/新增 fail-fast）。
- `testing-quality`: examples gate 与 pytest `public_api` suite MUST 覆盖同一份 public API catalog；当覆盖集合发生漂移时，`just qa` 必须 fail-fast 并输出差异。

## Impact

- 代码/示例：
  - `notebooks/marimo/example_public_api_suite/**`（新增/调整章节以覆盖 Tier1）
  - `tests/public_api/**`（补齐与 examples 对齐的最小回归断言）
  - `scripts/check-*.py` / `scripts/gen-*.py`（新增 gate + skill generator）
  - `packages/scalim-misc/src/scalim_misc/**`（实现 skill 生成器与可复用逻辑）
- Skills：
  - SSOT：`agentdev/skills/scalim-public-api/SKILL.md`（手工维护）
  - Generated：`agentdev/skills/scalim-public-api/references/**/*.gen.*`、`agentdev/skills/scalim-public-api/references/generated/**`（禁止手改；由 `just gen-*` 生成）
- 文档（如需串联展示）：
  - `docs/doc/**` 中的 `*.gen.*` 或 `BEGIN/END AUTOGEN:*` 区块仅通过 `just gen-docs` 刷新，禁止手改生成物/注入区块内部。

