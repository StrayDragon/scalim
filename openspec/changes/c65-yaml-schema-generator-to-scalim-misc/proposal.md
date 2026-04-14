## Why

当前 YAML DSL JSON Schema 的构建器（含生成期逻辑、fixture/snippet 读取、文档标准化 glue 等）仍位于 `src/scalim/`，导致：

- `src/scalim/` 需要同时承载运行期（Python 3.6）与生成期（dev）两套治理约束，`basedpyright strict`/coverage 等门禁的维护摩擦持续放大；
- 生成期逻辑与 runtime 逻辑混杂，使核心实现边界变厚，降低后续重构与演进速度；
- 更容易引入层级反转（例如 core 反向依赖 dev tooling packages），使依赖方向不可审计。

我们希望将“schema 生成/文档增强”这类 dev-only 能力下沉到 `packages/scalim-misc`，让 `src/scalim/` 回归为 schema SSOT（结构+描述）的单点真相，同时保持 `just qa` 的全仓库门禁不变。

## What Changes

- 将 YAML DSL JSON Schema 的生成器实现（builder / writer / docs standardization pipeline）迁移到 `packages/scalim-misc`（Python >=3.10）。
- `src/scalim/dsl/yaml_dsl/schema_dsl/**` 继续作为 schema SSOT：
  - dataclass + metadata（字段结构/约束/枚举引用）
  - 枚举、默认值与描述性文本（避免后续改字段时遗忘同步）
- 将当前 `schema_dsl/builder.py` 中内联的 workflow/scalim_yaml/imports 等“描述性 schema 片段”抽回到 `schema_dsl` 的 SSOT 模块（保持“描述在 core”的单点真相）。
- `scripts/gen-yaml-dsl-schema.py` 仍作为唯一生成入口，但改为调用 `scalim-misc` 中的生成器；CI 环境缺失 `scalim-misc` 时 fail-fast。
- 清理/禁止 core → `scalim-misc` 的导入（包含可选 hook 形态）；保持依赖方向单向：`scalim-misc` 可以依赖 `scalim`，但 `scalim` 不得依赖 `scalim-misc`。

## Capabilities

### New Capabilities
- （无）

### Modified Capabilities
- `yaml-dsl-schema`: schema SSOT/生成器边界与生成入口约束收敛（生成器迁移到 dev 包，SSOT 保留在 core，生成物位置不变）。
- `yaml-dsl-project-config-schema`: `scalim.yaml` schema 生成同样遵循上述边界。
- `module-organization`: 明确并门禁“runtime core 不得反向依赖 dev tooling packages（例如 `scalim-misc`）”。

## Impact

- 受影响代码：
  - `src/scalim/dsl/yaml_dsl/schema_dsl/`（抽取 SSOT 文案片段；移除/瘦身生成器实现）
  - `packages/scalim-misc/src/scalim_misc/`（新增/承载 schema generator）
  - `scripts/gen-yaml-dsl-schema.py`（生成入口改为调用 `scalim-misc`）
  - schema drift / generation 相关测试与治理门禁
- 对运行时用户：不影响 runtime compile/validate/run/workflow；不要求安装 `scalim-misc`。
- 对维护者：生成 schema（`just gen-yaml-dsl-schema`）需要 dev 环境包含 `scalim-misc`，CI 将强制该条件以避免静默降级。

