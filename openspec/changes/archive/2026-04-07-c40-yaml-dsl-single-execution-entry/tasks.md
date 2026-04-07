## 1. `scalim.yaml` 配置面收敛（BREAKING）

- [x] 1.1 将 `scalim.yaml yaml_dsl.editor` 全量替换为 `scalim.yaml yaml_dsl.lsp`（解析/类型/错误信息/文档示例一致）
- [x] 1.2 移除 `scalim.yaml yaml_dsl.runner.*`（解析、schema、文档与示例），并确保旧字段在 schema/校验层面 fail-fast（不做兼容）
- [x] 1.3 更新 `scalim.yaml` schema SSOT（`src/scalim/dsl/by_yaml/schema_dsl/**`）并运行 `just gen-yaml-dsl-schema` 生成 `src/scalim/dsl/by_yaml/schema/scalim_yaml.gen.json`（生成物禁止手改）

## 2. LSP/编辑器集成对齐新键名

- [x] 2.1 更新 `packages/scalim-yaml-dsl-lsp/**` 的 project discovery：读取 `yaml_dsl.lsp.python_roots` 与 `yaml_dsl.lsp.kind_overrides`（保持 nearest-wins 语义）
- [x] 2.2 更新 YAML DSL LSP code actions：
  - `Create minimal scalim.yaml` 生成的最小文件使用 `yaml_dsl.lsp.*`
  - `Add python roots` 写入 `yaml_dsl.lsp.python_roots`（不得写入旧 `yaml_dsl.editor.*`）
- [x] 2.3 更新编辑器文档（例如 `docs/doc/yaml-dsl/editor.md`、`docs/doc/yaml-dsl/lsp/troubleshooting.md`）与示例配置块，统一使用 `yaml_dsl.lsp`

## 3. 移除 CLI 执行入口（单执行入口 = Python）

- [x] 3.1 删除 `scalim-cli yaml-dsl run` 与 `scalim-cli yaml-dsl workflow run` 子命令（含参数/实现/帮助输出），并确保 `scalim-cli yaml-dsl --help` 不再出现 run 命令
- [x] 3.2 清理与 CLI runner 绑定的 `scalim.yaml` 默认值口径（`yaml_dsl.runner.*`）的所有文档/示例引用
- [x] 3.3 在文档中提供替代方案：最小 Python wrapper 示例（显式 `RunOptions.allowed_modules/allowed_functions`），用于“命令行一键执行”需求但不再通过 `scalim-cli` 执行

## 4. 文档/生成物与门禁

- [x] 4.1 若变更影响 docs 注入区块或 `.gen.` 文档，运行 `just gen-docs` 刷新并通过漂移门禁（禁止手改 `*.gen.*` 与 `BEGIN/END AUTOGEN:*` 区块内部）
- [x] 4.2 更新 YAML DSL skill 文档 SSOT（`artifacts/skills/scalim-yaml-dsl/**` 中的非生成文件），移除 CLI run 示例并对齐新 `scalim.yaml` 键名；必要时跑对应生成入口刷新 `*.gen.*`
- [x] 4.3 运行 `just qa` 与 `just openspec-check`（含 sanitize + `openspec validate`）确保质量门禁通过
- [x] 4.4 将本 change 下的增量 specs 同步回 `openspec/specs/**`（使用 `openspec-sync-specs` 工作流），并确保 specs 一致性与可验证性
