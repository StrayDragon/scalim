## Why

Imports v2 放开 `../` 与子目录后，跨 demand 复用会更顺，但也会带来两个后续治理问题：

1) **路径口径**：团队常想要一个稳定的“项目级根”（例如 `@/fragments/common.yaml`），避免相对路径在目录移动/拷贝时大面积改动。
2) **安全边界**：允许跨目录读取后，需要一个明确、可配置的“允许读取的 roots/aliases”，否则 imports 可能变成“任意读文件”的通道。

另外，scalim 自身也可能沉淀一组高复用的 YAML 片段（presets）。若每个项目都复制一份，维护与升级成本会很高，因此需要一种“引用 scalim 内置 presets”的语法与治理边界。

## What Changes

本变更是一个“提案保留”，不作为当前 imports v2 / render MVP 的交付物。

- `scalim.yaml`（可选）提供 imports 治理配置：
  - `yaml_dsl.import_aliases`：把 alias 前缀映射到目录（例如 `@` → `./`），使 YAML 内可写 `@/fragments/common.yaml`
  - `yaml_dsl.import_allowed_roots`（可选）：显式限制 imports 解析后的目标路径必须落在允许 roots 内（避免越界读取）
  - CLI 可提供 override（例如 `--import-root ...` / `--no-import-root-check`），用于 CI/容器差异化运行

- `scalim://...`（可选）引用 scalim 内置 presets：
  - `imports.std: "scalim://yaml-dsl/presets/common.yaml"`（示意）
  - 只读本地已安装 scalim 包资源（离线、不可走网络）
  - 建议以“白名单/注册表”管理 presets（而不是任意包内路径），以便做版本治理
  - `render_explain`（可选）记录每个导入片段的来源（file path / scalim preset id），保证 review/debug 可审计

## Capabilities

### New Capabilities
- `yaml-dsl-import-aliases-and-presets`: 通过 `scalim.yaml` 配置 imports aliases/allowed roots，并支持 `scalim://...` 引用 scalim 内置 YAML presets（只读、本地、可审计）

### Modified Capabilities
- `yaml-dsl-imports`: imports 路径解析需接入 aliases/roots 治理，并明确诊断信息格式
- `yaml-dsl-render-effective-yaml`: render 可选输出 provenance（`render_explain` 或等价接口），用于审计导入来源

## Impact

- 受影响代码（预期）：
  - imports 解析：`src/scalim/dsl/by_yaml/config_parsing/imports.py`
  - effective YAML 渲染 API：`src/scalim/dsl/by_yaml/config_parsing/`（读取 `scalim.yaml`、输出 explain 信息）
  -（若落地 presets）包内资源打包与读取（需要明确 SSOT 与发布策略）
- 受影响 schema/生成物（预期）：
  - schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/`
  - schema 生成物：`src/scalim/dsl/by_yaml/schema/*.gen.json`（通过 `just gen-yaml-dsl-schema` 刷新；禁止手改）
  - editor schema copy：`frontend/scalim-yaml-dsl-editor/public/schema/*.gen.json`（通过 `just gen-yaml-dsl-editor-schema` 刷新；禁止手改）
