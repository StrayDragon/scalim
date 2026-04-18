# public-api-agent-skill Specification

## Purpose
为 public API 能力演进提供一个可接手、可回归、可再生的 Codex skill：

- 在不引入“符号级硬 manifest SSOT”的前提下，把 Tier1 curated entrypoints、示例套件与 gate 串成确定性机制。
- 提供可复制的推荐导入与可运行样例索引，避免示例/skills 漂移导致“看起来能 import、但用法已过时”。

## ADDED Requirements

### Requirement: `scalim-public-api` skill MUST exist and be governed with generated references
系统 MUST 提供一个新的 skill：`agentdev/skills/scalim-public-api/`，并采用“手工 SKILL.md + 受控 generated references”的治理模型：

- `agentdev/skills/scalim-public-api/SKILL.md` MUST 为手工维护（SSOT）。
- 生成器 MUST 仅写入以下受控输出（禁止覆盖手工文件）：
  - `agentdev/skills/scalim-public-api/references/**/*.gen.*`
  - `agentdev/skills/scalim-public-api/references/generated/**`
- 系统 MUST 提供可重复运行的入口用于生成与校验：
  - `just gen-public-api-skill`
  - `just validate-public-api-skill`

#### Scenario: skill generator produces only managed outputs
- **WHEN** 维护者运行 `just gen-public-api-skill`
- **THEN** 系统 MUST 仅更新 skill 的受控 generated references
- **AND** MUST NOT 覆盖或重排 `agentdev/skills/scalim-public-api/SKILL.md`

#### Scenario: validate mode detects drift
- **GIVEN** 维护者修改了输入 SSOT（Tier1 markers / `__all__` / 示例套件结构）
- **WHEN** 维护者运行 `just validate-public-api-skill`
- **THEN** 若未刷新受控产物，校验 MUST fail-fast 并提示运行生成入口

### Requirement: generated references MUST be derived from Tier1 markers and `__all__` via static scanning
生成器 MUST 以以下 SSOT 为输入，并通过静态扫描（AST/text）生成确定性 references：

- Tier1 curated entrypoints：`src/scalim/**/__init__.py` markers（`# pragma: scalim-public-api tier1:...`）
- 每个入口模块的导出符号集合：该模块的 `__all__` 字面量（tuple/list of string literals）

生成器 MUST NOT 通过 `import` 目标模块来发现 markers 或 `__all__`（避免副作用与可选依赖导致的不稳定）。

#### Scenario: tier1 catalog output is deterministic
- **WHEN** 输入不变且重复运行 `just gen-public-api-skill`
- **THEN** 受控 references 输出 MUST 保持逐字节一致

### Requirement: skill references MUST map Tier1 entrypoints to runnable example coverage
生成器 MUST 为 Tier1 curated entrypoints 生成一个可审阅的“覆盖映射”参考，用于把稳定入口模块映射到可运行示例与回归门禁：

- examples（`notebooks/marimo/example_public_api_suite/` 的章节 SSOT）
- pytest（`tests/public_api/` 的最小闭环回归）
- headless gate（`just examples`）

覆盖映射 MUST 满足：
- 每个 Tier1 入口模块 MUST 至少对应一个被 examples gate 覆盖的章节
- 每个 Tier1 入口模块 MUST 同时被 pytest public_api suite 覆盖（直接或通过执行章节间接覆盖）

#### Scenario: missing tier1 coverage fails validation
- **GIVEN** Tier1 markers 新增了一个入口模块
- **WHEN** examples/pytest 覆盖未同步补齐
- **THEN** `just validate-public-api-skill` MUST fail-fast 并指出缺失模块

