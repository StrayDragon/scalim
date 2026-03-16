## 1. OpenSpec / Docs

- [x] 1.1 记录 fixture CLI 改名与 shim 策略(本 change 的 proposal/design/specs)
- [x] 1.2 更新 prompt-eval 文档,说明 `scalim-fixture-cli` 与 `scalim-cli` shim 的边界与排错步骤

## 2. Fixture CLI

- [x] 2.1 将 `openspec/prompt-eval/fixtures/agent_stub_project` 的 console script 从 `scalim-cli` 改为 `scalim-fixture-cli`
- [x] 2.2 更新 fixture CLI 的 `argparse(prog=...)` 与帮助文案,匹配新命令名

## 3. Workspace Setup (Isolation)

- [x] 3.1 `scripts/prompt-eval.py` 避免 `uv pip install -e .` 依赖 build 依赖/网络,改为在 workspace venv 的 `bin/` 下生成 `scalim-fixture-cli` 与 `scalim-cli`
- [x] 3.2 生成的脚本通过 `sys.path` 注入 `./src`,并确保 `uv run scalim-cli yaml-dsl ...` 可用(兼容现有 skill 模板)

## 4. Verification

- [x] 4.1 运行 `PROMPT_EVAL_LLM_DRY_RUN=1 just prompt-eval-agent-tmp ...` 确认 workspace 可准备且不污染仓库 `.venv`
- [x] 4.2 运行 `just openspec-check` 确认 OpenSpec 工件通过 sanitize/validate
