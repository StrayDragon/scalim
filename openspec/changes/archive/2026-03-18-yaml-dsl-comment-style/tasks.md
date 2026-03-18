## 1. CLI: remove schema server

- [x] 1.1 移除 `src/scalim/cli/yaml_dsl.py` 中 `yaml-dsl schema-serve` 子命令(参数注册 + dispatch)并同步帮助文本/错误信息
- [x] 1.2 移除或下线 `src/scalim/cli/yaml_dsl_lsp.py` 中仅用于 schema-serve 的 HTTP server 实现,确保无未使用入口残留

## 2. CLI: upsert-lsp-comment comment-style

- [x] 2.1 为 `yaml-dsl upsert-lsp-comment` 增加 `--comment-style {all,jetbrains,redhat}` 并设定默认值为 `all`
- [x] 2.2 调整 `src/scalim/cli/yaml_dsl_lsp.py` 的 upsert 逻辑: 支持同时 upsert 两种 modeline,并在 `jetbrains/redhat` 模式下移除另一种 modeline,保持幂等
- [x] 2.3 更新 `--schema-path` 默认值为“内置 schema 目录的本地绝对路径”(不依赖 `schema-serve`),并保持现有 type + base URL/dir + full json 的解析规则

## 3. Tests

- [x] 3.1 更新 `tests/test_yaml_dsl_lsp_comment.py` 覆盖 `--comment-style all/jetbrains/redhat` 三种行为与幂等性
- [x] 3.2 删除 `schema-serve` 相关回归测试,并确保测试集不再依赖内置 HTTP server

## 4. Specs (SSOT) + gates

- [x] 4.1 将 delta 规范同步到主规范 `openspec/specs/yaml-dsl-cli-validation/spec.md` 与 `openspec/specs/yaml-dsl-agent-guidance/spec.md` (SSOT; 非生成物)
- [x] 4.2 验收口径: 不编辑任何 `.gen.` 文件与 injected blocks; 运行 `just openspec-check` 与 `just qa` 确认 drift gate 通过
