## Meta

- Type: `refactor-0`
- Topic: YAML schema doc standardizer 从主包迁移到 `scalim-misc`（gen-only 能力下沉）
- Related code (当前实现位置):
  - `src/scalim/dsl/yaml_dsl/schema_dsl/doc_standardizer.py`（热点：`standardize_schema_docs`）
  - `src/scalim/dsl/yaml_dsl/schema_dsl/builder.py:12`（`from .doc_standardizer import standardize_schema_docs`）
  - 生成入口：`scripts/gen-yaml-dsl-schema.py` / `just gen-yaml-dsl-schema`

## 背景（Why）

当前 YAML schema 的 doc standardizer（递归生成 `markdownDescription`、fixture snippet 提取、最小示例骨架、enum 逐值语义校验等）属于 **gen-only** 的开发者能力，但现在实现落在 `src/scalim/`，在“主包必须 100% coverage”的治理下：

- 为了覆盖分支需要大量专用测试与边界兜底，维护成本高且与运行期价值不匹配
- dev-only 逻辑与 runtime 包代码同仓同治理，增加主包认知负担与重构阻力
- 生成器/fixtures/示例治理属于开发侧资产，不应要求库用户安装或承载其复杂度

我们需要把这类 gen-only 逻辑迁移到 `packages/scalim-misc`（开发者工具域），同时保持主包 schema SSOT 可被外部生成器自动导入，并且在缺少 `scalim-misc` 时主包不报错。

## 例子（为什么它更像 dev 工具而不是 runtime）

以 `schema_dsl/builder.py` 为例，它为了生成更友好的 schema docs，会尝试从仓库内的 notebooks/fixtures 提取 snippet（并在缺少这些文件时降级）。这类行为属于：

- 开发者体验（hover docs / 示例片段质量）
- 文档治理（枚举逐值语义一致性校验）
- 生成器管线（schema 输出可读性）

而不是 runtime 的核心能力（compile/validate/run/workflow）。把它放在主包会导致：

- runtime 包引入大量“只为生成/文档服务”的分支与依赖（即使最终运行时不会走）；
- coverage/治理成本显著上升。

## What Changes（推荐方案）

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
  - 生成器在开发/CI 环境 SHOULD 显式检查 `scalim-misc` 是否可用；若不可用：
    - CI 环境 MUST fail-fast（非零退出码）
    - 本地开发环境 SHOULD 输出明确 warning 并提示“生成结果将降级”（并给出安装 `scalim-misc` 的修复建议）

Non-goals（本提案不做）：
- 不改变 YAML DSL runtime compile/validate/run/workflow 的行为与性能边界
- 不改变最终发布的 `*.gen.json` schema 内容（在开发环境安装 `scalim-misc` 的前提下）

## 方案候选（优劣对比）

### 方案 A：保持在 `src/scalim/`（现状，不推荐）

优点：

- 不需要引入可选插件机制；
- 生成入口与实现同包，调用简单。

缺点：

- gen-only 逻辑被主包治理成本“强绑定”，长期维护摩擦大；
- 主包认知负担增加，影响 runtime 相关重构。

### 方案 B：迁移到 `packages/scalim-misc` + 主包可选 hook（本提案推荐）

优点：

- 主包回归“runtime 核心”，减少不必要复杂度；
- gen-only 能力在 dev 包内可更灵活地演进（测试/依赖/实现策略不必被主包约束）；
- hook 机制还能复用到其他 dev-only 插件场景（形成通用能力）。

缺点：

- 需要新增并维护一个“可选 dev 插件”加载点；
- 需要对生成器/CI 做“强制可用”门禁，避免静默降级。

### 方案 C：拆到独立仓库/包（不在本提案范围）

成本更高且治理复杂度更大，先不做。

## Capabilities

### New Capabilities
- `dev-optional-plugins`: 主包提供可选 dev 插件加载机制（仅用于生成期/开发侧工具，不进入 runtime 热路径）。

### Modified Capabilities
- `yaml-dsl-schema`: schema 生成管线中的 doc standardizer 阶段由可选 dev 插件提供；主包仅保留 schema SSOT 与插件 hook。
- `yaml-dsl-project-config-schema`: 同上（`scalim.yaml` 的 schema 文档标准化也由该 dev 插件提供）。

## Impact

- 受影响代码（预期）：
  - 主包：`src/scalim/dsl/yaml_dsl/schema_dsl/`（新增/调整一个极薄的可选 hook；移除/迁移 doc standardizer 主体）
  - dev 包：`packages/scalim-misc/src/scalim_misc/`（新增 schema doc standardizer 模块）
  - 生成入口：`just gen-yaml-dsl-schema` 仍为唯一 SSOT→生成物入口；仅在开发侧环境要求 `scalim-misc` 可用
- 对库用户的影响：
  - `scalim-misc` 仍为可选依赖；缺失时主包 MUST 正常导入与运行（dev 插件能力自动关闭）
- 风险与治理：
  - 风险：生成环境缺少 `scalim-misc` 导致 schema docs 降级
  - 缓解：生成器/QA 门禁在 dev/CI 环境对“schema docs 质量”做显式检查（避免静默漂移）

## 性价比（代价/收益）

- 代价：中（需要迁移模块 + 增加可选插件 hook + 调整生成器/CI 门禁 + 迁移测试）。
- 收益：高（主包简化、coverage 压力下降、dev-only 能力演进更顺畅）。
- 风险：中（主要风险是生成环境缺少 `scalim-misc` 造成 schema docs 降级；通过门禁可控）。

## 验证建议

- 生成一致性：
  - dev/CI 环境安装 `scalim-misc` 时，生成的 `*.gen.json` 不发生漂移（或漂移可解释且可接受）。
- 安装包环境降级：
  - 缺少 notebooks/fixtures 与缺少 `scalim-misc` 时，主包 import/运行不失败，且生成器给出明确提示（不允许静默低质量输出）。
