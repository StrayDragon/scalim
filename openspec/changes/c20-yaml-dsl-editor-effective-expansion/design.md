## Context

- YAML DSL authoring 中常见“展开语义”在 editor 里不可见:
  - anchors/aliases（模板复用）
  - merge key（`<<`）
  - nested list flatten（尤其是 `outputs[*].fields`）
  - imports/$import（demand 的跨文件复用）
- runtime/validator 已具备若干 SSOT 能力:
  - imports 展开：`scalim.dsl.yaml_dsl._internal.config_parsing.imports.expand_imports_inplace`
  - effective YAML dump：`scalim.dsl.yaml_dsl._internal.config_parsing.effective_yaml.dump_effective_demand_yaml`
  - outputs.fields 的 alias/object ref 校验与 flatten 语义（validator/parser 中已有逻辑）

编辑器侧的核心问题不是“能不能展开”，而是:
- 如何在**打开文档的内存态文本**上做展开（不依赖 mtime）；
- 如何在不引入 source-map 高成本的前提下，先补齐高 ROI 的导航/补全（Phase 1）。

## Goals / Non-Goals

**Goals:**
- 引入 editor 侧可复用的 “effective view”：
  - 输入以 LSP 内存态文本为准
  - 覆盖 anchors/aliases、merge key、nested list flatten（至少 `outputs[*].fields`）
  - demand 支持 imports/$import 展开（受 allowed-roots 约束）
- 基于 effective view 提升导航能力:
  - `outputs[*].fields` 内 field_id 的 hover/definition/completion
  - alias token（如 `*detail_fields`）支持 definition/hover（跳到 anchor，展示展开摘要）
- 引入缓存与失效:
  - doc 缓存按 `document_uri + document_version`（或文本 hash）
  - fragment 缓存按 `(path, mtime_ns)`，并支持并发 in-flight 去重

**Non-Goals:**
- 不追求“完全等价、可逆的 source-map 级 effective YAML”（作为 Phase 3 讨论）。
- 不改变 runtime 的 SSOT 语义；editor 侧只复用，不复制。

## Decisions

### 1) effective view 的定义与产物

- 对 demand YAML：
  1. 用 LSP 内存态文本解析为 mapping（安全 loader，允许 merge key）
  2. 调用 `expand_imports_inplace(raw_mapping, yaml_path=<anchor_path>, allowed_yaml_roots=<discovery>)` 展开 `$import`
  3. 基于展开后的 mapping 计算:
     - `FieldDefIndex`（复用 `collect_field_defs`）
     - `OutputsEffectiveIndex`（复用 outputs parser 的 flatten + field ref resolve 语义）
- 对 workflow YAML：
  - 仅做 anchors/aliases/merge key + flatten（不做 imports expansion，遵循 workflow 主线原则）

### 2) outputs.fields 导航: “先同文件，后跨文件”

- Phase 1（高 ROI）:
  - field_id 为字符串 → definition 跳到同文件 fields/source-fields 的声明点
  - alias token `*name` → definition 跳到 `&name` 的 anchor 声明点
  - completion/hover 基于同文件 `FieldDefIndex`
- Phase 2（中 ROI）:
  - 当 field 定义来自 import fragment：
    - fragment 缓存解析为 mapping + location index
    - 构建跨文件 `FieldDefIndex`（仅用于定位；不做全量 symbols）
    - definition 跳到 fragment 文件的声明点
- Phase 3（低 ROI/高成本）:
  - 讨论 source-map 级“有效 YAML 预览 + 可逆定位”（为复杂对拍/审阅服务）

### 3) 位置与别名的最小实现策略

- 同文件 anchor/alias 定位:
  - 通过 `ruamel.yaml` compose 解析扫描 `&anchor`/`*alias` token 的 mark，建立 `AnchorIndex`
  - alias hover 展示:
    - 展开后的元素数量
    - 前 N 个 field_id（避免长输出）
- 字段声明位置:
  - 复用 `build_yaml_location_index`（逻辑路径 → line/col）
  - definition 的 range 精度优先保证“可跳转”（必要时先用行首 range）

### 4) 缓存与并发策略

- doc 级缓存（server 内）:
  - key: `(uri, document_version)`
  - value: `parsed_mapping`、`location_index`、`field_def_index`、`outputs_effective_index`、`anchor_index`
- fragment 级缓存（shared core/server 任选其一实现）:
  - key: `(path, mtime_ns)`
  - value: `mapping`、`location_index`、`field_def_index`
- 并发去重:
  - 同 `(path, mtime_ns)` 的 fragment 解析使用 in-flight task 去重（依赖 `yaml-dsl-lsp-resolution-infra` 的基础设施）

### 5) 文档/生成边界与 drift gates（必须）

- 手工编辑范围:
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/**`
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/**`（仅在需要补“editor 复用入口”时）
- 禁止手改:
  - 任意 `*.gen.*` 与 `BEGIN/END AUTOGEN:*` 区块内部
- Drift gates:
  - `just qa`
  - `just openspec-check`

## Risks / Trade-offs

- [effective 语义与 runtime 漂移] → 强制复用 runtime 的 imports/outputs 解析逻辑；新增 helper 也放在 runtime 侧作为 SSOT。
- [跨文件定位成本] → Phase 2 只做“按需加载 fragment + 索引”，不做全量扫描；缓存 + in-flight 去重兜底。
- [anchor/alias range 复杂] → Phase 1 先保证 alias → anchor 的跳转可靠，复杂 source-map 留到 Phase 3。
