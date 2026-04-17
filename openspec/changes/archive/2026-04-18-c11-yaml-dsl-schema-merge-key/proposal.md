## Why

当前 `YAML DSL` 的 runtime 已明确支持 YAML merge key (`<<`) 语义，且在 imports 相关诊断里也鼓励用 `<<` 做 in-file reuse；但生成的 `JSON Schema` 在多处对 mapping key 使用了 `propertyNames` 正则约束（`^[a-zA-Z_][a-zA-Z0-9_]*$`），未包含 `<<`，导致 Red Hat `yaml-language-server`/`vscode-yaml` 在校验阶段报假阳性错误，进而干扰编辑器内联补全与校验体验。

该问题属于 **schema 与 runtime 支持不一致**：用户按官方推荐写法使用 `<<` 时，编辑器却提示“非法 key”，形成高频噪音并降低对 schema 校验的信任。

## What Changes

- 在 YAML DSL schema 生成链路中统一处理 merge key：
  - 对所有使用 `propertyNames` 约束 mapping key 的位置，显式允许 key 为 `<<`（在不放宽原有命名规则的前提下消除假阳性）。
  - 覆盖 `demand.gen.json`、`workflow.gen.json`、`scalim_yaml.gen.json` 中的 map-like object 节点，避免遗漏与后续回归。
- 增加最小回归用例/门禁，确保生成的 schema 在 YAML Language Server 下不再对 `<<` 报错（以 schema-only 体验为准，runtime 严格校验仍是最终裁决）。
- 文档/hover 描述与示例按需补齐：在适用的 mapping 节点说明 `<<` 属于允许的 YAML 语法（仅作为复用/merge；实际语义以 runtime 解析为准）。

## Capabilities

### New Capabilities
- （无）

### Modified Capabilities
- `yaml-dsl-schema`: 生成的 YAML DSL JSON Schema MUST 与 runtime 支持的 YAML merge key (`<<`) 语义对齐，避免编辑器侧假阳性并保持 schema-only 校验可用。

## Impact

- **SSOT (可编辑)**：
  - `src/scalim/dsl/yaml_dsl/schema_dsl/**`（schema DSL 元数据与常量）
  - `packages/scalim-misc/src/scalim_misc/yaml_schema_generator.py`（生成器：builder + writer + 标准化阶段）
- **生成物 (禁止手改)**：
  - `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`
  - `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json`
  - `src/scalim/dsl/yaml_dsl/schema/scalim_yaml.gen.json`
  - 刷新入口：`scripts/gen-yaml-dsl-schema.py` / `just gen-yaml-dsl-schema`
- **门禁/测试**：
  - schema drift gate 与（如需要）新增针对 merge key 的回归测试。

