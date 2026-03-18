## Why

最近一轮 YAML DSL 能力迭代（`{$init_var: ...}` 扩展到 `outputs.*.container.path`、`yaml-dsl validate` 默认严格 + best-effort JSONSchema、以及修复 `run_ir` 关闭阶段静默失败）使得校验/解析链路变得更复杂。

目前 YAML DSL 校验与指令解析存在重复实现与不一致行为（例如 schema 校验的“单条 vs 多条错误”、unknown-fields 的重复报错/漏报、`$init_var` 结构校验在 parser/runtime 各写一份）。这会增加下游迁移成本与回归风险，因此需要一次“收敛式”重构来稳定行为边界，并补齐回归测试基准。

## What Changes

- 统一 `{$init_var: <name>}` 指令节点的结构校验/错误路径策略，避免在 `outputs` parser 与 runtime 各自维护一套规则（保持“对象节点、编译期解析一次、缺失 fail-fast”的语义不变）。
- 重构 YAML DSL 的 schema 校验收集器，形成可复用的 schema issues 采集逻辑：
  - `yaml-dsl validate`：best-effort（缺依赖/非预期异常 → warning），不阻断内部语义校验。
  - `yaml-dsl schema validate`：schema-only（缺依赖 → error）。
  - 在 `jsonschema` 可用时使用 `Draft7Validator.iter_errors` 收集完整错误列表，并保证输出排序稳定。
- 修复/增强 unknown-fields 检测能力，使其在不依赖 `jsonschema` 的情况下仍能覆盖 `oneOf/anyOf/allOf` 等 schema 分支与数组 items（例如 `outputs[0]`），确保“默认 strict unknown fields”在所有环境下语义一致。
- 避免重复诊断：当 schema 校验与 unknown-fields 同时可产出同类诊断时，输出应去重并优先保留更可行动（含建议）的版本。
- 建立回归测试基准：覆盖 `jsonschema` 缺失/异常、`oneOf/anyOf` 下 unknown-fields（含 items）、重复诊断去重、以及 `outputs.*.container.path` 的 `$init_var` 解析与错误路径。
- 保持现有 CLI 交互形态：不新增 `--strict` 等开关；不将 `{$init_var: <name>}` 的 `<name>` 命名规则在所有上下文强行收紧为统一 pattern（避免引入破坏性变更）。

## Capabilities

### New Capabilities

<!-- 本次为重构与诊断一致性提升，不新增 capability -->

### Modified Capabilities

- `yaml-dsl-cli-validation`: 强化并统一 validate/schema-validate 的 schema/unknown-fields 行为（完整错误列表、oneOf/anyOf 覆盖、重复诊断去重、在无 jsonschema 环境下严格模式仍可靠）。

## Impact

- **SSOT / specs**: 行为变更以 `openspec/specs/yaml-dsl-cli-validation/spec.md` 为 SSOT；对应的 delta specs 存放于 `openspec/changes/c2-yaml-dsl-validation-refactor/specs/`。
- **代码影响面**(预期): `src/scalim/cli/yaml_dsl.py`、`src/scalim/dsl/by_yaml/config_parsing/validator.py`、`src/scalim/dsl/by_yaml/config_parsing/unknown_fields.py`，以及与 `outputs.*.container.path` 相关的 parser/runtime 辅助逻辑。
- **依赖/兼容性**: `jsonschema` 仍为可选依赖；所有运行时代码需保持 Python 3.6 兼容。
- **测试基线**: 新增/调整 pytest 回归用例；实施完成后以 `just test` 与 `just qa` 作为质量门禁，并运行 `just openspec-check` 校验 OpenSpec 工件一致性。
