# language: zh-CN
# capability: tools-prompt-eval-cli
# purpose: 定义 prompt-eval coding-agent workspace 的 fixture CLI 隔离策略，确保其不覆盖仓库真实 `scalim-cli`，同时保持 workspace 内 `uv run scalim-cli ...` 命令模板可复现，并避免对 PyPI build 依赖/网络造成的 dry-run 波动。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: tools-prompt-eval-cli

  @req:r81 @human
  场景: Fixture CLI 命令名与仓库 CLI 解耦
    - prompt-eval 的 workspace fixture MUST 提供一个内部专用的 CLI 命令名(例如 `scalim-fixture-cli`)用于执行 stub 行为。 该 fixture MUST NOT 注册与仓库真实 CLI 同名的 console script(例如 `scalim-cli`)。

  @req:r325 @human
  场景: Workspace venv 内提供 `scalim-cli` shim
    - 为保持 prompt-eval 的 skill 文档/断言中命令模板可复现,workspace 初始化 MUST 在 workspace 的本地 venv 内提供 `scalim-cli` shim。 该 shim MUST 将调用转发到 `scalim-fixture-cli`,且 shim 的作用域 MUST 限定在 workspace venv 内。

  @req:r448 @human
  场景: Workspace 初始化不污染仓库 `.venv` 且不依赖 PyPI build 依赖
    - prompt-eval 的 workspace 初始化 MUST NOT 将 fixture 包安装到调用方(仓库)虚拟环境。 workspace 初始化 MUST 避免通过 `uv pip install -e .` 安装 fixture(会引入 build 依赖并可能触发对 PyPI 的网络访问),而是通过在 workspace venv 的 `bin/` 目录生成 console script 来运行 fixture 代码。
  @req:r81 @human
  场景: fixture-被安装到任意虚拟环境也不覆盖仓库-cli
    - 必须成立：当 开发者/CI 将 prompt-eval fixture 安装到任意 Python 虚拟环境中；那么 该环境中不应产生/覆盖名为 `scalim-cli` 的 entrypoint
    当 开发者/CI 将 prompt-eval fixture 安装到任意 Python 虚拟环境中
    那么 该环境中不应产生/覆盖名为 `scalim-cli` 的 entrypoint
  @req:r325 @human
  场景: uv-run-scalim-cli-yaml-dsl-在-workspace-内可用
    - 必须成立：当 prompt-eval 生成 workspace 并在该 workspace 中运行 `uv run scalim-cli yaml-dsl validate <file>`；那么 命令应成功执行 fixture 的 stub 校验逻辑
    当 prompt-eval 生成 workspace 并在该 workspace 中运行 `uv run scalim-cli yaml-dsl validate <file>`
    那么 命令应成功执行 fixture 的 stub 校验逻辑
  @req:r448 @human
  场景: 运行-prompt-eval-不污染仓库-venv
    - 必须成立：当 开发者在仓库中运行 prompt-eval 的 workspace 初始化流程；那么 仓库 `.venv` 中不应出现 prompt-eval fixture 包
    当 开发者在仓库中运行 prompt-eval 的 workspace 初始化流程
    那么 仓库 `.venv` 中不应出现 prompt-eval fixture 包
