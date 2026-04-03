## Why

`demand` YAML 的主线应承载“需求本体”(sources/fields/relations/outputs 等),而 `include_full_error_message` / `validate_unique_field_names` 更像运行期的安全/隐私/治理策略。
它们一旦被复制粘贴进业务 YAML,会放大治理成本并造成“在不可信/CI 环境误开启”的风险;同时也破坏了 runtime policy 已迁出 YAML 的一致边界。

## What Changes

- **BREAKING**: `demand` YAML 主线不再允许顶层字段:
  - `include_full_error_message`
  - `validate_unique_field_names`
  - 若 YAML 仍包含这些字段,系统将 fail-fast 并给出迁移提示(改为通过 Python/CLI runtime entrypoints 配置)。
- 增加/收敛 Python/CLI runtime entrypoints 的 typed 配置面,以单个参数承载上述策略并提供默认值:
  - `demand_diagnostics: DemandDiagnosticsPolicy`
    - `include_full_error_message` 默认 `false`
    - `validate_unique_field_names` 默认 `true`
- `run demand` 与 `run workflow` 共享同一套 demand runtime-policy 注入逻辑(避免分叉/重复):
  - `run demand`: 通过 `demand_diagnostics=...` 配置
  - `run workflow`: 通过既有 `run_patches_by_id: Mapping[str, WorkflowRunPatch]` 做 per-run 覆盖(不新增额外 patch 参数)
- 同步更新文档/示例,移除 YAML 中的上述字段并引导迁移。
- 同步更新 YAML DSL JSON Schema 生成 SSOT,确保 schema 不再暴露这两个字段。

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `yaml-dsl-runtime-policy-boundary`: 将 `include_full_error_message` 与 `validate_unique_field_names` 纳入“必须迁出 YAML mainline 的 runtime policy 字段”清单,并补充迁移行为要求。
- `yaml-dsl-schema`: 移除“schema MUST 暴露 `validate_unique_field_names`”这一 authoring surface 要求;更新 schema 以不再包含 `include_full_error_message` / `validate_unique_field_names`。
- `output-composition`: 明确“落完整 error_message”的显式开关由 runtime entrypoints 控制(而不是 YAML authoring 字段)。

## Impact

- 影响代码路径:
  - `src/scalim/dsl/by_yaml/_internal/config_parsing/loader.py`: 顶层字段解析/报错迁移提示
  - `src/scalim/dsl/by_yaml/runtime/contracts.py` + `src/scalim/dsl/by_yaml/runtime/entrypoints.py` + `src/scalim/dsl/by_yaml/runtime/compiler.py`: runtime policy typed surface 与注入逻辑
  - `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`: 输出组合 spec 的策略参数来源
- 影响规范/文档:
  - OpenSpec: `openspec/specs/yaml-dsl-runtime-policy-boundary/spec.md`、`openspec/specs/yaml-dsl-schema/spec.md`、`openspec/specs/output-composition/spec.md`
  - Docs: `docs/doc/yaml-dsl/*` 与示例 YAML/Notebook(移除字段并迁移到 runtime 配置示例)
- 生成物治理:
  - `src/scalim/dsl/by_yaml/schema/*.gen.json` 与 `docs/doc/yaml-dsl/schema-reference.gen.md` 等为生成物,不得手工编辑;需改 SSOT 并通过 `just gen-docs`/相应生成入口刷新。
- 下游影响:
  - 任何依赖在 YAML 中设置上述字段的下游将需要迁移到 runtime entrypoints 参数;这是显式破坏性变更,但可换取更清晰的 authoring surface 与更可治理的安全策略边界。
