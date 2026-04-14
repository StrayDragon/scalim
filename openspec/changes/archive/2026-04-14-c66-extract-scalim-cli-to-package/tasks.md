## 1. 新建 packages/scalim-cli 与分发边界

- [ ] 1.1 创建 `packages/scalim-cli/pyproject.toml`（requires-python>=3.10）并在 workspace 中注册
- [ ] 1.2 提供 console script `scalim-cli`（入口 `scalim_cli.main:main`），并确保 `scalim-cli --help` 可运行
- [ ] 1.3 更新根 `pyproject.toml`：移除 `scalim` 主包的 `scalim-cli` scripts/旧 CLI extras，并更新 dev 依赖组以包含 `scalim-cli`

## 2. 迁移 CLI 实现并薄化（委托 service 层）

- [ ] 2.1 将 `src/scalim/cli/{main,yaml_dsl,yaml_dsl_lsp}.py` 迁移到 `packages/scalim-cli/src/scalim_cli/` 并修正导入路径
- [ ] 2.2 收敛 CLI 层职责：参数解析/渲染/退出码；校验逻辑全部委托 `scalim.dsl.yaml_dsl.validation_service`
- [ ] 2.3 批量更新仓库内对 `scalim.cli.*` 的引用（tests、`packages/scalim-misc`、docs/脚本等）

## 3. 重写与压缩 CLI tests

- [ ] 3.1 将 CLI 相关 tests 从 `tests/**` 中迁移并重组为“CLI 行为回归测试”（输出格式/exit code/关键子命令）
- [ ] 3.2 将语义矩阵测试下沉到 service 层（避免 CLI 白盒重复），删减重复用例并保持覆盖关键回归点
- [ ] 3.3 运行 `just qa` 确保全仓库门禁通过（pytest + lint + basedpyright + governance）

## 4. 文档与迁移说明

- [ ] 4.1 更新 docs/README：明确安装方式从 `scalim[cli]` 迁移为 `scalim-cli`
- [ ] 4.2 补充升级提示：`scalim` runtime 仍为 Python>=3.6；`scalim-cli` 为 Python>=3.10 的 dev 工具

