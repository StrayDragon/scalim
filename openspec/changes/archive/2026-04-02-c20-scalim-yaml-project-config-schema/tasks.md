## 1. Schema SSOT & Generation

- [x] 1.1 在 `src/scalim/dsl/by_yaml/schema_dsl/` 增加 `scalim.yaml` project config 的 schema SSOT（覆盖 `yaml_dsl.import_aliases/import_allowed_roots/editor.*`）
- [x] 1.2 扩展 schema builder 生成 Draft-07 JSON Schema（包含 `$schema/$id/$comment` 与必要的 type/enum 约束）
- [x] 1.3 扩展 `scripts/gen-yaml-dsl-schema.py` 与 `just gen-yaml-dsl-schema`，写出新生成物到 `src/scalim/dsl/by_yaml/schema/`（文件名按实现约定）

## 2. Drift Gate & QA

- [x] 2.1 扩展 schema generation drift test（例如 `tests/test_yaml_schema_generation.py`）覆盖新 schema 生成物
- [x] 2.2 验证 `just qa` 能捕获“修改 SSOT 未刷新生成物”的漂移场景

## 3. Docs / Editor Binding

- [x] 3.1 更新 `docs/doc/yaml-dsl/editor.md`：补充 `scalim.yaml` schema 的绑定方式（`$schema` header / YAML language server 配置示例）
- [x] 3.2 更新 `docs/doc/yaml-dsl/syntax.md`（如需要）：强调 `scalim.yaml` 仍为可选配置，并说明大型仓库可存在多层 `scalim.yaml`（nearest-wins，用于子项目隔离）
- [x] 3.3 若涉及 injected blocks/`.gen.` 文档，运行 `just gen-docs` 刷新并确保不手改生成物（本次未涉及 `.gen.` 文档或 injected blocks）

## 4. Optional Tooling

- [x] 4.1 （可选）扩展 `PROJECT_CLI_NAME yaml-dsl schema path/show` 或提供等价入口，便于脚本化获取 `scalim.yaml` schema 绝对路径
