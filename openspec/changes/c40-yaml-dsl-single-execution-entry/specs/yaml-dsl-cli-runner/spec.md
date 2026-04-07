## REMOVED Requirements

### Requirement: `scalim-cli yaml-dsl run` MUST run a demand YAML file
**Reason**：本仓库选择“单执行入口（Python）”，移除 CLI 执行入口以消除双入口与 `scalim.yaml` runner defaults 的误解空间。

**Migration**：使用 Python 入口 `scalim.dsl.by_yaml.run(...)` 执行，并显式装配 `RunOptions.allowed_modules/allowed_functions`。

#### Scenario: CLI no longer exposes demand run
- **WHEN** 用户尝试执行 `scalim-cli yaml-dsl run <demand.yaml>`
- **THEN** CLI MUST 返回非 0 退出码
- **AND** MUST 输出迁移提示（指向 Python `scalim.dsl.by_yaml.run`）

### Requirement: CLI runner MUST enforce allowlist (no implicit trust)
**Reason**：CLI runner 被移除；allowlist 语义由 Python `RunOptions` 统一承载并在 runtime 中 fail-fast。

**Migration**：在 Python 入口显式传入 allowlist（`RunOptions.allowed_modules/allowed_functions`）。

#### Scenario: missing allowlist is enforced by the only execution entrypoint
- **WHEN** 用户通过 Python 入口执行 YAML 且未提供 allowlist
- **THEN** 系统 MUST fail-fast（安全边界不放宽）

### Requirement: CLI runner MUST support `init_vars` injection via JSON
**Reason**：CLI runner 被移除；`init_vars` 注入仍由 Python `RunOptions.init_vars` 承载。

**Migration**：在 Python 入口将 JSON 解析为 mapping 后传入 `RunOptions.init_vars`。

#### Scenario: init_vars remain supported via Python execution
- **WHEN** demand YAML 使用 `{$init_var: <name>}` 指令节点
- **AND** 用户通过 Python 入口提供 `RunOptions.init_vars`
- **THEN** 系统 MUST 在编译期解析并应用注入值

### Requirement: CLI runner MUST support `template_vars` injection via JSON
**Reason**：CLI runner 被移除；模板变量注入仍由 Python `RunOptions.template_vars` 承载。

**Migration**：在 Python 入口将 JSON 解析为 mapping 后传入 `RunOptions.template_vars`。

#### Scenario: template_vars remain supported via Python execution
- **WHEN** demand YAML 包含 `{{ ... }}` 模板片段
- **AND** 用户通过 Python 入口提供 `RunOptions.template_vars`
- **THEN** 系统 MUST 在 YAML 解析前完成预编译并继续后续流程

### Requirement: `scalim-cli yaml-dsl workflow run` MUST run a workflow YAML file
**Reason**：CLI runner 被移除；workflow 执行统一收敛到 Python `scalim.dsl.by_yaml.run_workflow(...)`。

**Migration**：使用 Python 入口 `run_workflow` 执行 workflow，并显式装配 `RunOptions`。

#### Scenario: CLI no longer exposes workflow run
- **WHEN** 用户尝试执行 `scalim-cli yaml-dsl workflow run <workflow.yaml>`
- **THEN** CLI MUST 返回非 0 退出码
- **AND** MUST 输出迁移提示（指向 Python `scalim.dsl.by_yaml.run_workflow`）

### Requirement: CLI runner MUST read project defaults from `scalim.yaml`
**Reason**：`scalim.yaml` 不再承载 runner defaults；执行入口统一为 Python，运行期策略由调用方显式装配。

**Migration**：将原 `scalim.yaml yaml_dsl.runner.*` 的值移动到 Python 代码（例如应用/调度系统的 settings）并以 `RunOptions` 传入。

#### Scenario: scalim.yaml no longer contains runner defaults
- **WHEN** 用户在 `scalim.yaml` 中配置 `yaml_dsl.runner.*`
- **THEN** 系统 MUST 在校验/解析层面给出明确的“未知字段/不支持”错误（要求一次性升级配置）

## ADDED Requirements

### Requirement: CLI MUST be tooling-only and MUST NOT execute YAML DSL
系统 MUST 将 `scalim-cli yaml-dsl` 定位为 authoring/tooling 工具集合（schema/validate/editor integration），并且 MUST NOT 提供 demand/workflow 的执行子命令。

#### Scenario: yaml-dsl help does not list run commands
- **WHEN** 用户执行 `scalim-cli yaml-dsl --help`
- **THEN** 输出 MUST 不包含 `run` 或 `workflow run` 执行子命令

