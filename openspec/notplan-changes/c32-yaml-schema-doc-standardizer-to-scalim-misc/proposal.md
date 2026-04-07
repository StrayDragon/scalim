## Why

当前 YAML schema 的 doc standardizer（递归生成 `markdownDescription`、fixture snippet 提取、最小示例骨架、enum 逐值语义校验等）属于 **gen-only** 的开发者能力，但现在实现落在 `src/scalim/`，在“主包必须 100% coverage”的治理下：

- 为了覆盖分支需要大量专用测试与边界兜底，维护成本高且与运行期价值不匹配
- dev-only 逻辑与 runtime 包代码同仓同治理，增加主包认知负担与重构阻力
- 生成器/fixtures/示例治理属于开发侧资产，不应要求库用户安装或承载其复杂度

我们需要把这类 gen-only 逻辑迁移到 `packages/scalim-misc`（开发者工具域），同时保持主包 schema SSOT 可被外部生成器自动导入，并且在缺少 `scalim-misc` 时主包不报错。

## What Changes

- 引入主包内的“可选 dev 插件”扩展点（通用方式）：
  - 主包提供稳定的 hook（例如 `maybe_standardize_schema_docs(schema) -> schema`）
  - hook 内部使用 **ImportError-safe** 的 optional import 尝试加载 `scalim_misc` 的实现
  - 若 `scalim-misc` 不存在：该 hook MUST no-op（保证库用户零依赖、零失败）
- 将当前 doc standardizer 的主体逻辑迁移到 `packages/scalim-misc`：
  - 递归遍历与模板标准化（brief/full）
  - `$import` workaround 的表达
  - fixture snippets extractor（含 nested blocks 语义）
  - 示例渲染与最小骨架兜底策略
  - enum 逐值语义的校验/门禁逻辑
- 生成器脚本（`scripts/gen-yaml-dsl-schema.py`）保持“只依赖主包 schema SSOT”来构建 schema；当需要标准化时通过上述 hook 自动适配。
  - 生成器在开发/CI 环境 SHOULD 确保 `scalim-misc` 可用；若不可用，应提供清晰的失败/提示信息（避免静默生成低质量 schema）

Non-goals（本提案不做）：
- 不改变 YAML DSL runtime compile/validate/run/workflow 的行为与性能边界
- 不改变最终发布的 `*.gen.json` schema 内容（在开发环境安装 `scalim-misc` 的前提下）

## Capabilities

### New Capabilities
- `dev-optional-plugins`: 主包提供可选 dev 插件加载机制（仅用于生成期/开发侧工具，不进入 runtime 热路径）。

### Modified Capabilities
- `yaml-dsl-schema`: schema 生成管线中的 doc standardizer 阶段由可选 dev 插件提供；主包仅保留 schema SSOT 与插件 hook。
- `yaml-dsl-project-config-schema`: 同上（`scalim.yaml` 的 schema 文档标准化也由该 dev 插件提供）。

## Impact

- 受影响代码（预期）：
  - 主包：`src/scalim/dsl/by_yaml/schema_dsl/`（新增/调整一个极薄的可选 hook；移除/迁移 doc standardizer 主体）
  - dev 包：`packages/scalim-misc/src/scalim_misc/`（新增 schema doc standardizer 模块）
  - 生成入口：`just gen-yaml-dsl-schema` 仍为唯一 SSOT→生成物入口；仅在开发侧环境要求 `scalim-misc` 可用
- 对库用户的影响：
  - `scalim-misc` 仍为可选依赖；缺失时主包 MUST 正常导入与运行（dev 插件能力自动关闭）
- 风险与治理：
  - 风险：生成环境缺少 `scalim-misc` 导致 schema docs 降级
  - 缓解：生成器/QA 门禁在 dev/CI 环境对“schema docs 质量”做显式检查（避免静默漂移）
