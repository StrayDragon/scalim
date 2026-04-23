## Why

当一个 workflow 通过 `workflow.resources.{books,files}` 声明共享资源、并由多个 demand 通过 `outputs[*].to.book/to.file` 复用时，standalone 模式的 `scalim-cli yaml-dsl schema validate <demand.yaml>` 无法感知 workflow 级资源声明，导致出现“Unknown book id”之类的**假阳性**失败。

当前 workaround 是在每个 demand 内重复声明（或 `$import` 引入）同名资源 stub，以绕过 standalone 校验。这会带来：

- demand/workflow 双重声明同名资源，依赖 merge 语义覆盖，容易产生漂移与歧义
- 每个 demand 都要重复引入片段，增加维护与认知成本
- CI/IDE 侧 schema-only 校验结果与 workflow-level validate/运行时语义不一致

我们需要一个“可选上下文注入”的 schema-only 校验入口：在保持 standalone 严格校验能力的同时，允许在 demand 校验时显式加载 workflow 的资源声明，以消除假阳性并避免重复声明。

## What Changes

- `yaml-dsl schema validate` 新增可选参数：`--workflow <workflow.yaml>`
  - 当提供 `--workflow` 时，校验 demand YAML 时将 workflow 的 `workflow.resources.books/files` 视为可见声明（与 demand 本地 `resources.books/files` 做 union）。
  - 对 `outputs[*].to.book/to.file` 做资源存在性校验时，允许引用 workflow 级资源 id（仍保持 fail-fast；未知 id 仍为 error）。
- （一致性）demand 模式的 `yaml-dsl validate` 同步支持 `--workflow <workflow.yaml>`，保证 validate 与 schema validate 在“可见资源集合”口径上保持一致。
- 输出绑定校验覆盖两个资源面：
  - `to.book` ↔ `resources.books`
  - `to.file` ↔ `resources.files`

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `yaml-dsl-cli-validation`: `yaml-dsl schema validate`/`yaml-dsl validate` 在 demand 入口新增 `--workflow` 上下文参数，并在该上下文下对 outputs→resources 绑定执行一致的资源存在性校验（books + files）。

## Impact

- CLI 参数与行为：
  - `packages/scalim-cli/src/scalim_cli/yaml_dsl.py`（schema validate / validate 参数解析与执行）
- 运行时校验服务层（供 CLI/workflow validate 复用）：
  - `src/scalim/dsl/yaml_dsl/validation_service.py`（提取 workflow resources id、输出绑定校验 helper 的统一化）
- 测试：
  - `tests/yaml_dsl/**`（新增覆盖：`--workflow` 注入后 standalone demand 校验通过；以及 unknown id 仍 fail-fast）
- 文档/skill（如需要）：
  - `docs/doc/yaml-dsl/cli-reference.gen.md`、`agentdev/skills/scalim-yaml-dsl/**`（更新命令示例；通过既有生成入口刷新生成物/注入块）
