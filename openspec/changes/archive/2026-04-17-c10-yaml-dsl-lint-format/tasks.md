## 1. CLI: `yaml-dsl lint` / `yaml-dsl format`

- [ ] 1.1 在 `packages/scalim-cli/src/scalim_cli/yaml_dsl.py` 增加子命令 `yaml-dsl lint` 与 `yaml-dsl format`，补齐参数（`--fix/--json/--check/--diff`）与退出码（lint: 0/1/2；format: 0/1/2）
- [ ] 1.2 实现文件发现：支持文件/目录输入、递归扫描 `.yaml/.yml`，并默认排除 `.tmp/` 与 `dist/`
- [ ] 1.3 实现 format：对 `loader/call_by/compute/retry.should_retry` 的 string value 做幂等风格归一；仅在“去引号后仍解析为同一个 string”时移除引号；不得将 block scalar（`|`/`>` 及其变体）强制折叠为单行
- [ ] 1.4 实现 lint 规则（至少 `YDL001/YDL002/YDL004`）与稳定 rule code；实现 `--fix` 的 safe fixes（至少覆盖 `YDL001`）
- [ ] 1.5 为 lint/format 增加回归测试（复用 `tests/yaml_dsl/test_yaml_dsl_cli_output.py` 或新增测试文件）：覆盖 exit code、`--json` payload 可解析、`--fix` 行为与幂等性

## 2. Runtime: `call_by` multiline + `#` 注释（Python 3.6 边界）

- [ ] 2.1 更新 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/call_by.py`：支持 multiline 参数段内的 Python 风格 `#` 注释（不在 string literal 内），并确保注释不影响括号匹配与参数绑定（闭括号不被注释吞掉、注释里含 `)` 不提前匹配、允许 `)  # ...` 尾随注释）
- [ ] 2.2 增加 parser 单元测试：multiline + inline 注释 +（可选）trailing comma、注释中包含 `)`、close paren 行尾注释等覆盖

## 3. LSP: block scalar `loader/call_by` 可跳转 item（definition/hover/completion）

- [ ] 3.1 更新 `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/cursor_extraction.py`：对 YAML block scalar（`|`/`>`/`|-`/`|+` 等）内的 `loader/call_by` 实现光标抽取（head reference 与 kwargs RHS token），并返回“光标所在行”的精确 range（避免跨行 range 语义重写）
- [ ] 3.2 确认/调整 LSP server 在 definition/hover/completion 路径上复用新的抽取结果；YAML 解析失败或 partially-valid YAML 必须降级为“空结果 + warnings”（不得 crash）
- [ ] 3.3 扩展回归测试（优先在 `tests/yaml_dsl/test_yaml_dsl_cursor_extraction.py` 与 `tests/yaml_dsl/test_yaml_dsl_lsp_notebooks_regression.py` 增加覆盖）：block scalar 下 head ref 跳转、kwargs RHS token hover/definition/completion、空值 completion（`x=`）与带注释场景

## 4. Docs / Skills：示例风格对齐（SSOT vs 生成物）

- [ ] 4.1 在 CLI format 可用后，对 canonical YAML SSOT 执行一次风格归一：`notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml`（优先 plain scalar；长 `call_by` 用 block scalar；保留语义）
- [ ] 4.2 运行 `just gen-agent-skill` 重新生成 `agentdev/skills/scalim-yaml-dsl/references/*.gen.*` 与 `agentdev/skills/scalim-yaml-dsl/references/generated/**`（禁止手改生成物）
- [ ] 4.3 更新 `docs/doc/yaml-dsl/lsp/*.md`：补充 multiline `call_by` 推荐写法与“不丢跳转”的说明，并在合适位置提及 `yaml-dsl lint/format` 的团队执行入口；最后运行 `just gen-docs` 刷新 `docs/site/**`（生成物禁止手改）

## 5. 规范同步与验收门禁

- [ ] 5.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/yaml-dsl-cli-validation/spec.md`、`openspec/specs/field-compute/spec.md`、`openspec/specs/yaml-dsl-editor-semantics-core/spec.md`、`openspec/specs/yaml-dsl-lsp-server/spec.md`、`openspec/specs/yaml-dsl-agent-guidance/spec.md`、`openspec/specs/yaml-dsl-lsp-editor-integration-guides/spec.md`
- [ ] 5.2 运行 `just qa` 与 `just openspec-check` 作为最终验收门禁

