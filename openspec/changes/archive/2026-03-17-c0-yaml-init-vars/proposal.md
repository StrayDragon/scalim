## Why

当前 `{$runtime: <name>}`/`runtime_vars` 的命名容易误导用户把它理解为“运行期动态求值/表达式”,但实际语义是 **编译期注入的初始化变量**。该误解会带来:
- YAML authoring 的心智负担与误用(例如尝试字符串插值或期待运行期变更)
- 设计讨论与实现边界不清晰(尤其在 workflow/IR 演进前,需要更稳定、可解释的指令命名)

因此需要将该能力更名为 `{$init_var: <name>}`/`init_vars`,让语义与实际实现一致,并在全仓一次性升级旧写法(不做兼容兜底)。

## What Changes

- **BREAKING**: 将 loader params 模板中的 `{$runtime: <name>}` 指令节点更名为 `{$init_var: <name>}`
  - 适用范围不变: 仅 `main_source.params` 与 `sources.<id>.params`
  - 语义不变: 仍在编译期解析并落成不透明 literal,后续不会被 `$keys/$rows` 再次扫描
  - 缺失变量仍 fail-fast,但错误信息与提示文本更新为 `init_var/init_vars`

- **BREAKING**: 将 by_yaml 运行入口与契约中的 `runtime_vars` 更名为 `init_vars`
  - `scalim.dsl.by_yaml.run/compile/run_workflow(...)` 入口参数更名
  - `RunOptions.runtime_vars` 更名为 `RunOptions.init_vars`

- 文档/Schema/示例同步升级
  - JSON Schema hover 文案与示例统一使用 `{$init_var: <name>}`
  - 更新相关 docs/fixtures/tests,并通过 `just gen-yaml-dsl-schema`/`just gen-docs`/`just qa`/`just openspec-check`

### SSOT / Generated Boundary (MUST)

- SSOT:
  - 指令解析与错误: `src/scalim/dsl/by_yaml/params_template.py`
  - schema hover 文案 SSOT: `src/scalim/dsl/by_yaml/schema_dsl/constants.py` (及同目录下 schema DSL)
- Generated (禁止手改):
  - `src/scalim/dsl/by_yaml/schema/demand.gen.json`, `src/scalim/dsl/by_yaml/schema/workflow.gen.json` (由 `scripts/gen-yaml-dsl-schema.py` 生成)
  - `frontend/**/schema/*.gen.json` (由 `just gen-yaml-dsl-editor-schema` 生成)
  - docs 中的 `.gen.` 与 injected blocks (由 `just gen-docs` 生成/注入)

## Capabilities

### New Capabilities
- （无）

### Modified Capabilities
- `yaml-runtime-vars`: 将 `runtime_vars`/`{$runtime: ...}` 更名为 `init_vars`/`{$init_var: ...}`，并保持编译期解析与 fail-fast 行为不变
- `demand-dsl`: `params` 模板中对运行期变量指令的描述与限制同步更新为 `{$init_var: ...}`
- `dsl-runtime-structure`: adapter 在 `DemandConfig -> DemandIr` 前解析运行期变量指令的要求同步更新为 `init_var`
- `source-cache`: `preload_forever` 与 params 模板/注入变量的契约同步更新为 `init_var/init_vars`
- `yaml-dsl-schema`: schema hover/文案/示例中对运行期变量指令的说明同步更新为 `{$init_var: ...}`
- `yaml-dsl-micro-tunes`: 与运行期变量指令相关的微调/迁移提示同步更新为 `{$init_var: ...}`

## Impact

- Python API:
  - 运行入口参数重命名会影响所有调用方(`run/compile/run_workflow`)
- YAML authoring:
  - 所有使用 `{$runtime: ...}` 的 demand YAML 必须升级为 `{$init_var: ...}`
- Schema/Docs:
  - 需要更新 schema 生成物与 editor schema 镜像,并回归 docs 生成与示例
- Tests:
  - 需要覆盖: 新旧指令的校验、缺失变量 fail-fast、旧写法明确报错提示、workflow preload 冲突签名路径不受影响
