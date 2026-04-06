# dsl-runtime-structure (delta) Specification

## ADDED Requirements

### Requirement: by_yaml entrypoints MUST accept a single `RunOptions` object
系统 MUST 将 by_yaml facade 的运行入口收敛为 options-object 形态：

- `run(yaml_path, *, options: RunOptions) -> RunResult`
- `compile(yaml_path, *, options: RunOptions) -> Compilation`

该 `RunOptions` MUST 作为运行期 knobs 的唯一承载对象（allowlist、模板、imports roots、并行、重试、护栏、overrides 等），以避免继续扩大公开函数签名。

#### Scenario: options-object drives compile and run
- **GIVEN** 调用方构造 `RunOptions(allowed_modules=..., batch_size=..., template_vars=...)`
- **WHEN** 调用方执行 `run("path/to/demand.yaml", options=options)`
- **THEN** 系统 MUST 使用该 `RunOptions` 完成加载/编译/执行
- **AND** 运行行为 MUST 与同等配置通过旧入口实现时一致

## MODIFIED Requirements

### Requirement: official facade MUST preserve current extension seams

在公共表面收敛过程中，系统 MUST 保持当前已确认的受控扩展点继续可经由官方 facade 使用，而不是通过删减能力来完成“收敛”。

本轮至少包括（均通过 `RunOptions` 承载并注入）：

- `sink`
- `components`
- `allowed_modules` / `allowed_functions`
- `allowed_yaml_roots`

系统 MUST 破坏性移除 by_yaml facade 的 Python-only 输出注入扩展点:
- `run/compile` 不再接受 `output_composition=...`
- `RunOptions` 不再暴露 `output_composition` 字段

execution 层内部仍会使用编译产物 `OutputCompositionSpec` 表达 composed outputs,但该对象不再作为 by_yaml facade 的可注入扩展点。

#### Scenario: public facade remains behavior-complete for supported extension seams
- **WHEN** 调用方通过 `IMPL_ROOT.dsl.by_yaml.run(..., options=RunOptions(...))` 或 `compile(..., options=RunOptions(...))` 使用上述受控扩展点
- **THEN** 系统 MUST 继续支持这些能力
- **AND** 公共表面收敛 MUST 体现为“入口与契约明确”,而不是静默删除这些受支持能力

### Requirement: YAML DSL 官方入口为 `IMPL_ROOT.dsl.by_yaml`
系统 MUST 提供 `IMPL_ROOT.dsl.by_yaml` 作为 YAML DSL 的官方入口(导入路径),用于承载调用方最常用的稳定接口.

该官方入口 MUST 以“受控 re-export”方式提供最小 facade,并 MUST 导出以下符号:
- 运行入口: `run` / `compile` / `run_workflow`
- 运行期契约: `UNSET`、`ResolverTrustedMode`、`RunOptions`、`RunOverrides`、`Compilation`、`RunResult`

该官方入口 MUST 保持精简:
- MUST NOT 通过包根 re-export `schema_dsl`、`config_parsing` 等大域对象或内部实现细节.
- MUST 通过显式 `__all__` 白名单限制导出面,避免公共 API 膨胀.

#### Scenario: 调用方可通过 IMPL_ROOT.dsl.by_yaml 导入运行入口与 options/overrides 契约
- **WHEN** 调用方执行 `from IMPL_ROOT.dsl.by_yaml import run, compile`
- **AND** 调用方执行 `from IMPL_ROOT.dsl.by_yaml import RunOptions, RunOverrides, ResolverTrustedMode`
- **THEN** 导入 MUST 成功且行为与现有实现一致
