## 1. Schema 与 project config（SSOT/生成边界）

- [x] 1.1 更新 schema SSOT：将 `yaml_dsl.import_aliases/import_allowed_roots` 合并为 `yaml_dsl.import_roots`（`src/scalim/dsl/by_yaml/schema_dsl/models/scalim_yaml.py`）
- [x] 1.2 更新 `scalim.yaml` 解析：实现 `import_roots` 解析与校验（alias 唯一、path 必须为存在目录且不越界）（`src/scalim/dsl/by_yaml/_internal/config_parsing/project_config.py`）
- [x] 1.3 运行 schema 生成入口并提交生成物（禁止手改）：`just gen-yaml-dsl-schema`

## 2. Runtime imports（单一语义 + 去冗余）

- [x] 2.1 更新 imports 展开：用 `import_roots` 同时提供 alias 重写与默认 allow-roots 扩展（`src/scalim/dsl/by_yaml/_internal/config_parsing/imports.py`）
- [x] 2.2 移除/合并 “import_allowed_roots 二次校验” 逻辑，确保仅存在单一 allow-roots gate（同上）
- [x] 2.3 更新错误信息/diagnostics 文案：从旧键迁移到 `yaml_dsl.import_roots`（同上）
- [x] 2.4 迁移并补齐单测：覆盖 import_roots 解析、alias 重写、越界 fail-fast（`tests/yaml_dsl/test_yaml_dsl_imports.py`、`tests/yaml_dsl/test_yaml_dsl_project_config.py`）

## 3. CLI validate（默认行为与 project config 对齐）

- [x] 3.1 调整 `--allowed-yaml-root` 默认值为未提供(None)，确保未显式指定时会读取 `scalim.yaml` 的默认推导（`src/scalim/cli/yaml_dsl.py`）
- [x] 3.2 补充/更新 CLI 回归测试：覆盖“无 flag 读取 scalim.yaml import_roots”的场景（tests 目录内对应文件）

## 4. LSP shared core / server（imports 一致性 + code actions）

- [x] 4.1 更新 LSP core：project discovery 从 `import_roots` 推导 `allowed_yaml_roots` 与 alias 重写输入（`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py`）
- [x] 4.2 更新 `$import` definition/hover 解析：使用 `import_roots` 重写 imports 路径解析（同上）
- [x] 4.3 更新 Quick Fix：将 `scalim.yaml.addImportAllowedRoots` 替换为 `scalim.yaml.addImportRoots`（含 `minimal|wide`），并同步文档/测试（server + tests）

## 5. Docs / skills / drift gates

- [x] 5.1 更新 docs：将 `import_aliases/import_allowed_roots` 文档迁移到 `import_roots`（`docs/doc/yaml-dsl/**`）
- [x] 5.2 刷新生成物/注入区块（禁止手改生成物）：`just gen-docs`、`just gen-agent-skill`
- [x] 5.3 运行 `just openspec-check` 校验 OpenSpec 工件一致性

## 6. 验收与质量

- [x] 6.1 运行仓库 QA 门禁：`just qa`
- [x] 6.2 编写迁移说明（release note / docs 段落），给出旧→新配置示例与常见坑的解释
