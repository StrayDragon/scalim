## Context

YAML schema doc standardizer（递归生成 `markdownDescription`、fixture snippet 提取、最小示例骨架、enum 逐值语义校验等）属于 **gen-only** 的开发者能力：它服务于 schema 生成与文档质量，而不属于 runtime compile/validate/run/workflow 的核心能力。

当前该逻辑位于 `src/scalim/`，在“主包 100% coverage”的治理下带来持续摩擦：

- 为覆盖分支需要大量专用测试与兜底，而这些逻辑对运行期价值不匹配；
- dev-only 逻辑与 runtime 核心同包同治理，增加主包认知负担并阻碍 runtime 重构；
- schema 生成器会尝试读取 notebooks/fixtures 等仓库资产（缺失时降级），这更像开发侧管线而非库用户应承载的复杂度。

本 refactor-0 目标是：将 doc standardizer 下沉到 `packages/scalim-misc`（开发者工具域），主包只保留一个 ImportError-safe 的可选 hook，使库用户不需要安装 `scalim-misc` 也能正常 import/运行；而在开发/CI 的 schema 生成环境中，`scalim-misc` 必须可用以保证 schema docs 质量不降级。

## Goals / Non-Goals

**Goals:**

- 将 doc standardizer 主体逻辑迁移到 `packages/scalim-misc`
- 主包提供稳定且极薄的可选 dev 插件 hook：
  - optional import（ImportError-safe）
  - 插件缺失时 no-op（主包运行不失败）
- `scripts/gen-yaml-dsl-schema.py` 仍以主包 schema SSOT 为入口构建 schema，并通过 hook 自动接入标准化步骤
- 在 dev/CI 的生成环境中对“标准化能力缺失”建立显式门禁/提示，避免静默生成低质量 schema

**Non-Goals:**

- 不改变 YAML DSL runtime 行为与性能边界
- 不改变发布的 `*.gen.json` schema 内容（在 dev 环境安装 `scalim-misc` 的前提下应保持一致）

## Decisions

### 1) 主包提供 ImportError-safe 的标准化 hook（方案 B）

在主包 schema 生成管线中引入一个稳定 hook（示例命名）：

- `maybe_standardize_schema_docs(schema) -> schema`

实现要求：

- hook 内部仅做 optional import 尝试加载 `scalim_misc` 的实现
- 若 `scalim-misc` 不存在：MUST no-op 并返回原 schema（保证库用户零依赖、零失败）
- hook 必须不进入 runtime 热路径（只在 schema 生成器/开发侧调用）

### 2) 将 doc standardizer 逻辑迁移到 `packages/scalim-misc`

迁移范围包括：

- schema docs 递归标准化与模板生成
- fixtures/snippets extractor（含 nested blocks 语义）
- enum 逐值语义校验/门禁逻辑
- 最小示例骨架渲染与兜底策略

`scalim-misc` 作为 dev 工具包可更灵活地引入测试与依赖，不再被主包 100% coverage 强绑定。

### 3) 插件缺失策略：CI fail-fast，本地 warning 且提示降级

为防止 schema docs 质量在生成环境中被静默降级：

- `scripts/gen-yaml-dsl-schema.py` 或 `just gen-yaml-dsl-schema` SHOULD 显式检查插件是否可用
- 当插件缺失时：
  - **CI 环境**：MUST fail-fast（非零退出码），避免生成低质量 schema docs 并把降级结果提交/上传为工件
  - **本地开发**：SHOULD 输出明确 warning 并提示“生成结果将降级”（并给出可操作修复建议：安装 `scalim-misc` 并重新生成）

## Risks / Trade-offs

- **生成环境依赖差异**：主包可在无 `scalim-misc` 下运行，但生成环境必须有；需通过 just/CI 门禁把依赖差异显式化，避免“本机生成没标准化”导致 drift。
- **输出漂移风险**：迁移过程中可能出现 `markdownDescription` 文案顺序/空白差异；通过 schema drift guard（`tests/test_yaml_schema_generation.py`）兜底，并在迁移期锁定生成输出。

## Migration Plan

- Phase 0：在主包引入 hook（no-op fallback）+ 在 `scalim-misc` 落地实现 + 生成器接入 hook
- Phase 1：迁移/调整相关测试与文档治理门禁，确保 dev/CI 生成环境必须使用 `scalim-misc` 标准化结果

## Open Questions

- 无。
