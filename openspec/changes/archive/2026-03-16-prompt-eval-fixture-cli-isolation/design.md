## Context

prompt-eval 的 coding-agent 套件会为每个 test case 生成独立 workspace,并在其中创建 uv venv,安装一个最小 fixture 项目用于提供 YAML DSL 相关的 stub CLI。当前 fixture 使用 `scalim-cli` 作为 console script 名称,在以下场景会产生破坏:

- fixture 被误装进仓库开发 venv 时,覆盖真实 `scalim-cli` 的 entrypoint,导致 CLI 行为与报错不可预期。
- fixture 以 editable 方式指向临时 workspace 路径,当临时目录被删除后,开发 venv 中的 entrypoint/导入会变成悬空引用。

此外,现有 workspace 初始化虽然尝试从 PATH 中移除激活 venv 的 `bin`,但仍可能在 `uv` 的环境推断下发生“装错环境”的情况,需要更强的确定性。

## Goals / Non-Goals

**Goals:**
- prompt-eval 的 fixture CLI MUST 不与仓库真实 CLI 冲突(即使被误装进开发 venv,也不应覆盖 `scalim-cli`)。
- prompt-eval 的 workspace MUST 保持现有命令链路可用(继续支持 skill 文档中 `uv run scalim-cli yaml-dsl ...` 模板)。
- workspace 初始化 MUST 明确把依赖安装进 workspace 本地 venv,避免污染调用方环境。
- 变更应尽量局部,不引入额外依赖,不改变 promptfoo/provider 行为。

**Non-Goals:**
- 不在本提案中修改/实现 YAML DSL 新能力(例如 dense_rank/partition/top_k 语义)。
- 不重命名或迁移仓库真实的 `scalim-cli`。
- 不把 prompt-eval fixture 提升为对外发布/支持的 CLI。

## Decisions

1. **Fixture CLI 改名**: 将 prompt-eval fixture 注册的 console script 从 `scalim-cli` 改为 `scalim-fixture-cli`。
   - 备选方案: 继续使用 `scalim-cli` 但确保永不装进开发 venv；该方案对“误装/环境泄漏”不够鲁棒。

2. **Workspace 内提供 shim**: workspace 初始化在本地 venv 的 `bin/` 生成 `scalim-cli` shim,转发到 `scalim-fixture-cli`。
   - 这样 skill 文档/断言/step-count 规则无需改动,且 shim 作用域被限制在 workspace venv 内。

3. **不依赖 editable install**: workspace 初始化避免 `uv pip install -e .`(会引入 build 依赖,且可能需要访问 PyPI),改为在 workspace venv 的 `bin/` 目录直接生成 `scalim-fixture-cli` 与 `scalim-cli` 脚本,并通过 `sys.path` 注入 `./src` 来运行 fixture 代码。
   - 这样既能避免“装错环境”,也能降低 dry-run 对网络/缓存的偶然依赖。

4. **文档化边界与修复路径**: prompt-eval 文档中明确:
   - `scalim-fixture-cli` 仅供 prompt-eval 内部使用；
   - `scalim-cli` shim 仅存在于 prompt-eval 生成的 workspace venv；
   - 若开发 venv 已被污染,给出恢复步骤。

## Risks / Trade-offs

- [shim 与真实 CLI 语义不同] → 缓解: shim 仅在 prompt-eval workspace 内存在,且 fixture 的职责被明确为“最小可复现 stub”,不承诺覆盖真实 CLI 的全部语义。
- [uv 行为变化导致安装失败] → 缓解: 使用 `-p <workspace python>` 显式指定安装目标；失败时输出清晰错误信息并停止。
- [开发 venv 既有污染仍需人工清理] → 缓解: 文档提供一键恢复命令(卸载 fixture/重装仓库包)与症状识别方式(`which scalim-cli`)。
