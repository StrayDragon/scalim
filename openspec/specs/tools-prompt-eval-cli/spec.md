# prompt-eval-fixture-cli Specification

## Purpose
定义 prompt-eval coding-agent workspace 的 fixture CLI 隔离策略，确保其不覆盖仓库真实 `scalim-cli`，同时保持 workspace 内 `uv run scalim-cli ...` 命令模板可复现，并避免对 PyPI build 依赖/网络造成的 dry-run 波动。

## Related Concepts
- Agent workspace 生成脚本 (scripts/prompt-eval.py)
- Fixture 代码与 stub CLI (agentdev/prompt-eval/fixtures/agent_stub_project/)
- 维护与排错说明 (docs/doc/dev/prompt-eval-agent.md)

## Requirements
### Requirement: Fixture CLI 命令名与仓库 CLI 解耦
prompt-eval 的 workspace fixture MUST 提供一个内部专用的 CLI 命令名(例如 `scalim-fixture-cli`)用于执行 stub 行为。
该 fixture MUST NOT 注册与仓库真实 CLI 同名的 console script(例如 `scalim-cli`)。

#### Scenario: fixture 被安装到任意虚拟环境也不覆盖仓库 CLI
- **WHEN** 开发者/CI 将 prompt-eval fixture 安装到任意 Python 虚拟环境中
- **THEN** 该环境中不应产生/覆盖名为 `scalim-cli` 的 entrypoint
- **AND** 应产生名为 `scalim-fixture-cli` 的 entrypoint

### Requirement: Workspace venv 内提供 `scalim-cli` shim
为保持 prompt-eval 的 skill 文档/断言中命令模板可复现,workspace 初始化 MUST 在 workspace 的本地 venv 内提供 `scalim-cli` shim。
该 shim MUST 将调用转发到 `scalim-fixture-cli`,且 shim 的作用域 MUST 限定在 workspace venv 内。

#### Scenario: `uv run scalim-cli yaml-dsl ...` 在 workspace 内可用
- **WHEN** prompt-eval 生成 workspace 并在该 workspace 中运行 `uv run scalim-cli yaml-dsl validate <file>`
- **THEN** 命令应成功执行 fixture 的 stub 校验逻辑

### Requirement: Workspace 初始化不污染仓库 `.venv` 且不依赖 PyPI build 依赖
prompt-eval 的 workspace 初始化 MUST NOT 将 fixture 包安装到调用方(仓库)虚拟环境。
workspace 初始化 MUST 避免通过 `uv pip install -e .` 安装 fixture(会引入 build 依赖并可能触发对 PyPI 的网络访问),而是通过在 workspace venv 的 `bin/` 目录生成 console script 来运行 fixture 代码。

#### Scenario: 运行 prompt-eval 不污染仓库 `.venv`
- **WHEN** 开发者在仓库中运行 prompt-eval 的 workspace 初始化流程
- **THEN** 仓库 `.venv` 中不应出现 prompt-eval fixture 包
- **AND** workspace 的本地 venv 的 `bin/` 下应存在 `scalim-fixture-cli` 与 `scalim-cli` 可执行入口
