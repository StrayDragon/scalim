# yaml-dsl-cli-runner Specification

## ADDED Requirements

### Requirement: `scalim-cli yaml-dsl run` MUST run a demand YAML file
系统 MUST 提供 CLI 子命令 `scalim-cli yaml-dsl run <demand.yaml>` 用于运行单个 demand YAML 文件。

该命令 MUST 复用现有 by_yaml 运行入口的核心链路（解析/校验/编译/执行），并且不要求用户编写 Python wrapper 才能跑通 YAML。

#### Scenario: run demand YAML with file outputs
- **GIVEN** 一个 demand YAML 在 `resources.files` 与 `outputs` 中声明了 CSV 输出
- **WHEN** 用户执行 `scalim-cli yaml-dsl run demand.yaml` 并提供必要的运行期参数（例如 allowlist）
- **THEN** CLI MUST 以退出码 0 结束
- **AND** MUST 在声明的输出路径生成对应文件

#### Scenario: run demand YAML without outputs (summary-only)
- **GIVEN** 一个 demand YAML 未声明 `outputs`（因此不会写出任何文件）
- **WHEN** 用户执行 `scalim-cli yaml-dsl run demand.yaml` 并提供必要的运行期参数（例如 allowlist）
- **THEN** CLI MUST 以退出码 0 结束（当运行成功时）
- **AND** CLI MUST 输出可操作的执行摘要（例如 total_rows/duration 等）
- **AND** CLI MUST 提示“当前未声明 outputs,因此不会落盘”,并指向补齐 outputs 或使用 Python `RunOverrides.*` 的方式

### Requirement: CLI runner MUST enforce allowlist (no implicit trust)
CLI runner MUST 保持与当前运行时一致的安全边界：

- 若调用方未提供 allowlist（通过 CLI flags 或项目默认配置），CLI MUST fail-fast（退出码非 0）
- CLI MUST NOT 引入“默认允许任意 import”的隐式模式

#### Scenario: missing allowlist fails fast
- **GIVEN** 用户执行 `scalim-cli yaml-dsl run demand.yaml`
- **AND** 未通过 CLI flags 或项目默认配置提供 `allowed_modules/allowed_functions`
- **WHEN** CLI 尝试运行该 YAML
- **THEN** CLI MUST 失败并返回非 0 退出码
- **AND** 错误信息 MUST 提示用户如何配置 allowlist（示例命令或指向 `scalim.yaml yaml_dsl.runner.allowed_modules`）

### Requirement: CLI runner MUST support `init_vars` injection via JSON
CLI runner MUST 支持通过 JSON 文件注入 `init_vars`（mapping），并将其传递给 by_yaml runtime 以解析 `{$init_var: ...}` 指令节点。

#### Scenario: init_vars are applied during compile
- **GIVEN** demand YAML 的 `main_source.params` 或 `resources.files.*.path` 使用 `{$init_var: output_path}`
- **WHEN** 用户执行 `scalim-cli yaml-dsl run demand.yaml --init-vars-json vars.json`
- **THEN** CLI MUST 将 `vars.json` 解析为 mapping 并传递给 runtime
- **AND** 运行应成功解析该 `init_var` 并按注入的路径写出

### Requirement: CLI runner MUST support `template_vars` injection via JSON
CLI runner MUST 支持通过 JSON 文件注入 `template_vars`（mapping），并将其传递给 by_yaml runtime 的 template precompile 阶段。

#### Scenario: template_vars are applied before YAML parsing
- **GIVEN** demand YAML 包含 `{{ ... }}` 模板片段
- **WHEN** 用户执行 `scalim-cli yaml-dsl run demand.yaml --template-vars-json vars.json`
- **THEN** CLI MUST 将 `vars.json` 解析为 mapping 并传递给 runtime
- **AND** 运行应成功渲染并继续后续的 imports/校验/编译/执行流程

### Requirement: `scalim-cli yaml-dsl workflow run` MUST run a workflow YAML file
系统 MUST 提供 CLI 子命令 `scalim-cli yaml-dsl workflow run <workflow.yaml>` 用于运行 workflow YAML 文件。

#### Scenario: workflow run executes all nodes
- **GIVEN** 一个 workflow YAML 声明了至少两个 `workflow.runs[*]`
- **WHEN** 用户执行 `scalim-cli yaml-dsl workflow run workflow.yaml` 并提供必要的运行期参数（例如 allowlist）
- **THEN** CLI MUST 执行所有可达节点并生成其声明的输出（若声明）
- **AND** CLI MUST 以退出码 0 结束（当 workflow 运行成功时）

### Requirement: CLI runner MUST read project defaults from `scalim.yaml`
当入口 YAML 文件所在项目存在可发现的 `scalim.yaml` 时，CLI runner MUST 读取其中 `yaml_dsl.runner` 的默认值作为运行参数来源，并允许 CLI flags 覆盖。

#### Scenario: project defaults reduce repeated flags
- **GIVEN** 项目根存在 `scalim.yaml` 且包含 `yaml_dsl.runner.allowed_modules`
- **WHEN** 用户在该项目内执行 `scalim-cli yaml-dsl run demand.yaml`（不显式传 `--allowed-module`）
- **THEN** CLI MUST 使用 `scalim.yaml` 中的默认 allowlist 运行
