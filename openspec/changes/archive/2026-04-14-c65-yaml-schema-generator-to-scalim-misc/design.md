## Context

YAML DSL JSON Schema 生成属于开发期治理能力：它服务于编辑器结构提示、schema-only 校验与文档质量，但不属于 runtime compile/validate/run/workflow 的核心热路径。

当前 schema 生成实现（尤其是 `schema_dsl/builder.py`）仍位于 `src/scalim/`，并且混入了多类 dev-only 逻辑：

- 生成期对仓库内 fixture/snippet 的探测与读取（缺失时降级）；
- schema docs 标准化（枚举语义校验、markdownDescription 模板化等）；
- workflow/scalim.yaml 等 schema 的大量内联描述片段（难以作为 SSOT 被复用与审计）。

这使 `src/scalim/` 的边界变厚：既要保持 Python 3.6 运行时约束，又要为生成期逻辑承担额外 QA/类型治理摩擦。与此同时，我们希望保持一个关键原则：

- **描述性信息（字段含义/约束解释）必须留在 `src/scalim`**，作为 schema SSOT 的单点真相；
- dev tooling packages（例如 `scalim-misc`）可以消费 SSOT，但 core 不得反向依赖这些包。

## Goals / Non-Goals

**Goals:**

- 将 YAML DSL JSON Schema 生成器实现迁移到 `packages/scalim-misc`（Python >=3.10），降低 core 的维护/治理负担。
- 保持 `src/scalim/dsl/yaml_dsl/schema_dsl/**` 为 SSOT：字段结构（dataclass+metadata）、枚举/默认值、以及用户可见描述文本。
- 将 builder 中内联的描述性 schema 片段抽取为 core SSOT 模块，避免“描述散落在生成器实现里”导致更新遗忘。
- 保持生成入口与生成物边界不变：
  - 生成入口仍为 `scripts/gen-yaml-dsl-schema.py` / `just gen-yaml-dsl-schema`
  - 输出仍写入 `src/scalim/dsl/yaml_dsl/schema/*.gen.json`（禁止手改）
- 明确并守护依赖方向：`scalim-misc -> scalim` 单向，`scalim` 不得导入 `scalim-misc`（包括 optional hook 形态）。

**Non-Goals:**

- 不改变 YAML DSL runtime 的行为、性能边界与错误口径。
- 不改变生成物路径与文件名。
- 不在本变更中改动 YAML DSL LSP/VSCode 相关模块组织（仅确保 schema 生成链路仍可用）。

## Decisions

### 1) 将 schema SSOT 与生成器实现分层：core 负责“描述符”，misc 负责“生成”

约定：

- `src/scalim/dsl/yaml_dsl/schema_dsl/**` 仅承载 SSOT（结构/枚举/文案），并保持 Python 3.6 兼容；
- `packages/scalim-misc` 承载生成器实现（遍历 dataclass metadata、拼装 JSON Schema、写文件、应用 docs standardizer），可使用 Python >=3.10 的开发侧能力。

这将把“描述性信息”与“生成算法/治理管线”解耦：字段变更只需改 core SSOT，生成器自动消费，降低遗漏风险。

### 2) 将 builder.py 内联的描述片段抽取为 core SSOT 模块

对 workflow/scalim.yaml/imports 等 schema 片段：

- 将其 `description/markdownDescription/default/enum` 等描述性信息抽取到 `schema_dsl` 下的 SSOT 模块（例如 `*_ssot.py` 或 `schema_fragments.py`），并通过显式导出供生成器使用；
- 生成器只负责“引用这些片段并组装 schema”，不再成为文案 SSOT。

### 3) 生成入口保持单点：scripts 调 misc generator，CI 强制可用

- `scripts/gen-yaml-dsl-schema.py` 仍是唯一生成入口。
- 该脚本在生成时必须依赖 `scalim-misc`（CI fail-fast，避免静默生成降级文案/片段）。
- 本地开发环境仍应提供明确提示与修复建议（例如同步 dev 依赖或使用 workspace 安装）。

### 4) 移除 core → scalim-misc 的 optional import hook

由于标准化与生成器整体下沉到 `scalim-misc`，core 不再需要通过 `importlib` 去加载 `scalim-misc`。此举可以：

- 明确依赖方向（避免层级反转被“optional hook”掩盖）；
- 减少 runtime import 路径的不确定性（虽然 hook no-op，但仍是一条反向依赖通道）。

## Risks / Trade-offs

- **输出漂移风险** → 通过现有 drift gate（`just gen-yaml-dsl-schema` + tests）兜底；迁移后必须重新生成并提交 `*.gen.json`，禁止手改生成物。
- **工具链依赖差异（本地 vs CI）** → 在 `scripts/gen-yaml-dsl-schema.py` 中显式检查并在 CI fail-fast；在本地给出可操作提示，避免“本机生成没有标准化”导致漂移。
- **类型/治理分层边界不清** → 在 specs 中明确 SSOT 与生成物边界，并在 tasks 中加入依赖方向检查与验收口径。

