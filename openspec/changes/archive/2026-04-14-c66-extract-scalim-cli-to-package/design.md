## Context

仓库当前将 CLI 实现放在 `src/scalim/cli/**`，虽然它在 coverage 上被视为“非 core 边界”，但仍然：

- 占用 `src/scalim` 的模块空间与依赖心智；
- 迫使 CLI 的演进受到 Python 3.6 运行时边界的牵制；
- 使大量 CLI-only tests 与变更回归都需要在“核心运行时”目录树里进行维护。

与此同时，YAML DSL 的校验逻辑已经在 `scalim` 内形成了可复用的 service 层（例如 `dsl/yaml_dsl/validation_service.py`），CLI 的最佳定位应是：args → service → renderer。

因此，本设计将 CLI 拆成独立发行物 `scalim-cli`（位于 `packages/scalim-cli`，requires-python >=3.10），并将 CLI 的实现与测试治理迁移到该包中。

## Goals / Non-Goals

**Goals:**

- 提供独立发行物 `scalim-cli`：
  - 在 `packages/scalim-cli` 中实现并分发 `scalim-cli` console script；
  - requires-python >=3.10（明确 CLI 为 dev 工具，不再被 runtime 3.6 约束）。
- 将 CLI 实现从 `src/scalim/cli/**` 迁移到新包，并保持对外命令树与关键输出契约不变（参见 `yaml-dsl-cli-validation`）。
- 进一步薄化 CLI：核心校验逻辑 MUST 委托 `scalim` 的 service 层；CLI 只做参数解析、渲染与退出码决策。
- 重构 tests：
  - service 层的语义正确性由 `scalim` 内测试覆盖；
  - CLI 包侧保留少量高价值行为回归测试（输出格式/exit code/关键子命令）。

**Non-Goals:**

- 不新增 YAML DSL 的执行子命令（CLI 仍为 tooling-only）。
- 不改变 YAML DSL runtime 的接受/拒绝语义与错误口径（仅迁移入口与组织）。
- 不提供 `scalim.cli` 的兼容层（除非后续明确要求兼容）。

## Decisions

### 1) 新包命名与入口

- 发行名：`scalim-cli`
- import root：`scalim_cli`（与现有 workspace 包命名对齐，如 `scalim_yaml_dsl_lsp`）
- console script：`scalim-cli = scalim_cli.main:main`

### 2) CLI 依赖策略

- `scalim-cli` 依赖 `scalim`（复用其 runtime/service 层）。
- CLI 侧依赖（例如 `jsonschema`）由 `scalim-cli` 自身承担，不再通过 `scalim[cli]` 这样的 runtime extras 间接提供。
  - 目标是降低下游“命令存在但缺依赖”的摩擦，并使安装边界更清晰。

### 3) 迁移范围与模块映射

迁移 `src/scalim/cli/` 的模块到 `packages/scalim-cli/src/scalim_cli/`，保持模块职责不变但允许清理/压缩：

- `src/scalim/cli/main.py` → `scalim_cli/main.py`
- `src/scalim/cli/yaml_dsl.py` → `scalim_cli/yaml_dsl.py`
- `src/scalim/cli/yaml_dsl_lsp.py` → `scalim_cli/yaml_dsl_lsp.py`

其中 `yaml_dsl.py` 中的校验路径 MUST 继续复用 `scalim.dsl.yaml_dsl.validation_service` 作为语义 SSOT。

### 4) tests 重构策略：收敛 CLI 回归面

- 将 CLI 侧测试从“模块导入/内部函数白盒”收敛为“命令行为 + 渲染契约”：
  - `--json` payload shape
  - linter-style 输出的关键行格式
  - exit code 策略
  - schema path/show / upsert-lsp-comment 的幂等门禁
- 对 YAML 语义校验矩阵（unknown fields/legacy fields/workflow validate 等）优先在 service 层测试覆盖，减少 CLI 侧重复矩阵维护。

## Risks / Trade-offs

- **BREAKING：安装方式变化** → 通过 docs 更新与清晰提示缓解；在 release notes/upgrade guide 中明确从 `scalim[cli]` 迁移到 `scalim-cli`。
- **仓库内引用漂移**（tests/工具脚本/misc 包）→ 在迁移任务中一次性批量替换 `scalim.cli.*` 导入点，并以 `just qa` 兜底。
- **CI/本地环境 Python 版本差异** → `scalim-cli` 明确 requires-python>=3.10；repo 的 dev 依赖组也已要求 3.10+，对贡献者成本可控。

