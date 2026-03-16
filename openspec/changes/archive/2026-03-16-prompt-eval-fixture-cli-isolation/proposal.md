## Why

当前 prompt-eval (coding-agent / promptfoo) 的 workspace fixture 会通过 `uv pip install -e .` 安装一个 stub CLI 来支持 `uv run scalim-cli yaml-dsl ...` 的命令链路。由于该 fixture 也注册了同名 console script,一旦被误装进仓库的开发虚拟环境,会覆盖真实 `scalim-cli`,导致本机 CLI 行为被“劫持”(甚至指向已被删除的临时目录)。

我们需要让默认 prompt-eval 工作流在行为上与仓库开发环境解耦,避免污染与隐性破坏(尤其是覆盖 `scalim-cli` 入口)。

## What Changes

- **BREAKING**: prompt-eval fixture 不再注册 `scalim-cli` console script,改为注册内部专用命令 `scalim-fixture-cli`。
- prompt-eval workspace 初始化时,在 workspace 本地 uv venv 中生成一个 `scalim-cli` shim,将调用转发到 `scalim-fixture-cli`(保证现有 skill 文档/断言仍可用,且不影响仓库真实 CLI)。
- prompt-eval workspace 初始化在本地 uv venv 的 `bin/` 下直接生成 `scalim-fixture-cli` 与 `scalim-cli` 脚本,通过 `sys.path` 注入 `./src` 来运行 fixture 代码,避免 `uv pip install -e .` 引入 build 依赖与对 PyPI 的网络依赖(降低 dry-run 波动)。
- 更新 prompt-eval 相关文档/注释,解释 fixture CLI 与 shim 的边界与故障排查方式。

## Capabilities

### New Capabilities
- `prompt-eval-fixture-cli`: prompt-eval 的 fixture CLI 与仓库真实 CLI 解耦,并保证 workspace 内命令链路可复现且不污染开发环境。

### Modified Capabilities

## Impact

- 影响范围: `openspec/prompt-eval/fixtures/**`, `scripts/prompt-eval.py`, prompt-eval 文档。
- 对运行时/用户侧 `scalim-cli` 无影响；仅影响 prompt-eval fixture 与其 workspace 生成逻辑。
- 已被污染的开发 venv 需要手动清理(卸载 fixture 并重装本仓库 CLI),否则 `scalim-cli` 仍可能指向旧入口。
