## 1. Docs: 默认启动方式改为 `uvx`

- [ ] 1.1 更新 `docs/doc/yaml-dsl/lsp/index.md`：将默认启动方式收敛为 `uvx scalim-yaml-dsl-lsp serve ...`，并保留 “installed 二进制在 PATH” 的备选方式与适用场景说明
- [ ] 1.2 更新 `docs/doc/yaml-dsl/lsp/neovim.md`：默认示例使用 `uvx`（command + args / 单字符串两种形态），并补充 installed 模式的等价配置
- [ ] 1.3 更新 `docs/doc/yaml-dsl/lsp/zed.md`：默认示例使用 `uvx`（`binary.path` + `arguments`），并补充 installed 模式的等价配置
- [ ] 1.4 更新 `docs/doc/yaml-dsl/lsp/jetbrains.md`：默认示例使用 `uvx`（Command/Arguments），并补充 installed 模式的等价配置
- [ ] 1.5 更新 `docs/doc/yaml-dsl/lsp/troubleshooting.md`：所有 `scalim-yaml-dsl-lsp ...` 命令优先给出 `uvx` 版本，并以注释/小节保留 installed 版本

## 2. LSP CLI：初始化失败提示包含 `uvx` 兜底路径

- [ ] 2.1 更新 `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/cli.py`（或等价入口）：当 serve 初始化失败/依赖缺失时，stderr 的可操作提示同时包含 `uv tool install scalim-yaml-dsl-lsp` 与 `uvx scalim-yaml-dsl-lsp serve --log-level INFO` 两条修复路径；并确保 stdout 不输出半截 JSON-RPC
- [ ] 2.2 为该错误提示补齐回归测试（复用或新增 `packages/scalim-yaml-dsl-lsp` 下的测试）：断言非 0 exit code、stdout 为空、stderr 包含上述两条提示

## 3. 规范同步与验收门禁

- [ ] 3.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/yaml-dsl-lsp-editor-integration-guides/spec.md` 与 `openspec/specs/yaml-dsl-lsp-serve/spec.md`
- [ ] 3.2 运行 `just gen-docs` 刷新 docs-site（`docs/site/**` 为生成物，禁止手改）
- [ ] 3.3 运行 `just qa` 与 `just openspec-check` 作为最终验收门禁

