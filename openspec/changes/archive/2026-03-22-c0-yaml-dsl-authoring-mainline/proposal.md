## Why

当前 YAML DSL 的可复用性与可审计性有两个“真痛点”：

1) `imports/$import` 的 V1 路径约束过严（同目录文件名），在多 demand 项目里会逼迫 fragments 平铺或复制粘贴，导致 drift 与 review 成本飙升。
2) 复用（imports / anchors / template）一旦变多，作者很难用“最终等价配置”做对拍；缺少一个稳定的 `render effective YAML` 工具链入口，debug/review 都靠猜。

## What Changes

- Imports v2（在不引入远程/包管理的前提下升级路径能力）：
  - `imports.<alias>` 支持：`./x.yaml`、`../x.yaml`、`x.yaml`、`x/y.yaml`
  - 路径解析基准：当前 YAML 文件所在目录（demand.yaml 与 fragments 一致；确定性）
  - 仍拒绝：绝对路径、任意 URI scheme（`*://...`，含 `file://`/`http(s)://`/`scalim://`）、预留 alias 前缀（例如 `@/x.yaml`、`COMMON:/x.yaml`）（避免把 imports 变成“任意读取通道”）

- 库 API 增加 `render effective YAML`（用于 review/debug/对拍）：
  - 新增：`load_effective_demand_yaml(...)` / `dump_effective_demand_yaml(...)` 这类 `loads/dumps` 形态 API（由模板预编译 + imports 展开得到“单文件等价配置”）
  - 输出约束：移除 `imports/$import`（已展开），保留 `{$init_var: ...}` / `$keys` / `$rows` 等指令节点（它们属于运行期模板 AST）
  - 目的：让“复用/装配”从黑盒变成可审计产物，支撑 review/debug/对拍门禁（CLI 可后续基于该 API 再补）

- Authoring 主线治理（不强行改语法形状，只把边界写清楚）：
  - 主线 authoring 仍是单文件 `demand.yaml`，并明确 `outputs` 留在主文件（便于 aggregate/metrics 用 anchors/alias 复用）
  - 明确 `init_vars` vs `template_vars` 的阶段差异与混用注意事项，避免误判“变量冲突”

## Capabilities

### New Capabilities
- `yaml-dsl-render-effective-yaml`: 提供库侧 `loads/dumps` 形态 API 输出 effective YAML（用于 review/debug/对拍）

### Modified Capabilities
- `yaml-dsl-imports`: 放宽 imports 路径规则到 v2（支持 `../` 与子目录路径），并补齐诊断与规范文字

## Impact

- 受影响代码（预期）：
  - imports 解析与诊断：`src/scalim/dsl/by_yaml/config_parsing/imports.py`
  - effective YAML 渲染 API：`src/scalim/dsl/by_yaml/config_parsing/`（新增 `loads/dumps` 形态入口，并在必要时对外 re-export）
  - schema SSOT 与生成物：
    - SSOT：`src/scalim/dsl/by_yaml/schema_dsl/`
    - 生成物：`src/scalim/dsl/by_yaml/schema/*.gen.json`（禁止手改；通过 `just gen-yaml-dsl-schema` 刷新）
    - editor schema copy：`frontend/scalim-yaml-dsl-editor/public/schema/*.gen.json`（通过 `just gen-yaml-dsl-editor-schema` 刷新）
- 受影响示例/门禁（预期）：
  - marimo fixtures（若使用 imports 需升级写法）：`notebooks/marimo/demo_big_data_report/by_yaml_dsl/`
  - 生成物：`notebooks/marimo/marimo_coverage.gen.md`（禁止手改；通过 `just gen-marimo-coverage` 刷新）
- 风险与对策（摘要）：
  - `../` 引入的“读文件边界”问题：MVP 先禁用 URI/绝对路径；若要边界治理，通过显式 roots/aliases 配置，而不是推断 git repo root
