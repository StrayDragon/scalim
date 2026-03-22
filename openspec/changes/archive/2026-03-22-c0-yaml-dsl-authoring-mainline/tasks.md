## 0. 边界与基线（先写死口径）

- [x] 0.1 明确本变更的 SSOT/生成物边界（schema / editor schema / marimo coverage）并在 PR 描述中写出对应 `just` 入口
- [x] 0.2 跑一遍基线命令，记录现状行为与失败信息（用于对拍）：`scalim-cli yaml-dsl validate` / `scalim-cli yaml-dsl schema validate`
- [x] 0.3 将临时文档目录 `_YAML_DSL_FINAL/` 的内容收敛到本 OpenSpec change（proposal/design/specs/tasks）并移除该目录

## 1. Imports v2（路径解析 + 诊断）

- [x] 1.1 升级 `src/scalim/dsl/by_yaml/config_parsing/imports.py::_normalize_import_path()`：支持 `./` / `../` / 子目录；仍要求 `.yaml/.yml`；拒绝绝对路径、任意 URI scheme（`*://...`）与预留 alias 前缀（例如 `@/x.yaml`）
- [x] 1.2 保持解析基准为当前 YAML 文件所在目录（确定性）；错误信息包含“原始值 + 解析基准 + 归一化后的绝对路径（若可算）”
- [x] 1.3 补齐/更新单测（若已有 imports tests 就扩展，否则新增最小覆盖）：至少覆盖 sibling/child/parent + 绝对路径/URI 拒绝

## 2. Render API（effective YAML）

- [x] 2.1 新增库侧 `loads/dumps` 形态 API：`load_effective_demand_yaml` / `dump_effective_demand_yaml`（template precompile 仅在显式提供 template vars 时启用）+ imports expansion
- [x] 2.2 输出约束：dump 内容不含 `imports/$import`，并保留 `{$init_var: ...}` 等指令节点（运行期模板 AST；不尝试保留 anchors/alias）
- [x] 2.3 增加最小单测：基础渲染、imports expansion 失败时抛出可诊断错误信息

## 3. Schema（SSOT → 生成物）同步

- [x] 3.1 更新 schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/builder.py::_imports_schema()` 的 pattern/描述为 v2 语义
- [x] 3.2 运行 `just gen-yaml-dsl-schema`（刷新 `src/scalim/dsl/by_yaml/schema/*.gen.json`；禁止手改）
- [x] 3.3 运行 `just gen-yaml-dsl-editor-schema`（刷新 `frontend/.../public/schema/*.gen.json`；禁止手改）
- [x] 3.4 验收：`just qa` drift check 通过

## 4. Fixtures / 门禁对拍

- [x] 4.1 若 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/` fixtures 使用 imports：统一升级到 v2 路径写法
- [x] 4.2 运行 `just gen-marimo-coverage`（刷新 `notebooks/marimo/marimo_coverage.gen.md`；禁止手改）
- [x] 4.3 验收：`just examples` 通过

## 5. OpenSpec 校验与规范同步

- [x] 5.1 运行 `just openspec-check`
- [x] 5.2 变更完成/归档前，将本 change 的 delta specs 同步回 `openspec/specs/`（例如 `yaml-dsl-imports`、新增 `yaml-dsl-render-effective-yaml`）
