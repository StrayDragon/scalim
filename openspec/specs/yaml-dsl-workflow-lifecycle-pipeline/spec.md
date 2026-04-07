# yaml-dsl-workflow-lifecycle-pipeline Specification

## Purpose
TBD - created by archiving change c0-yaml-dsl-workflow-lifecycle-pipeline. Update Purpose after archive.
## Requirements
### Requirement: workflow runtime MUST implement a lifecycle pipeline with explicit phase results
系统 MUST 将 workflow 的生命周期实现为一组显式阶段（phase pipeline），并为每个阶段提供可被测试消费的阶段结果对象（phase result），以便：
- 将阶段顺序变成 SSOT（避免多入口各自拼装导致 drift）
- 使边界约束“靠数据结构表达”（早期阶段结果不暴露后期阶段所需信息）
- 让单测可以在不启动 engine 的情况下覆盖 boundary 行为

#### Scenario: pipeline can be executed up to preflight without starting the engine
- **GIVEN** 一份合法的 workflow YAML
- **WHEN** 测试仅执行 pipeline 到 preflight 阶段
- **THEN** 系统 MUST 能得到包含 per-run effective options 的阶段结果
- **AND** workflow engine MUST NOT 被启动

### Requirement: structural preload MUST remain parser-only and MUST NOT consume runtime-only diagnostics
workflow 对 runs 的结构预加载（preload/compile）MUST 只消费结构信息（outputs/resources/dependency wiring），并且 MUST NOT 运行任何依赖 effective runtime policy 的 diagnostics。

#### Scenario: workflow structural preload accepts duplicate display names regardless of validate_unique_field_names
- **GIVEN** 某个 run 引用的 demand fields 存在 duplicate effective field display names
- **WHEN** 系统执行 structural preload（workflow compile/preload 阶段）
- **THEN** preload MUST 成功返回结构信息
- **AND** 系统 MUST NOT 在该阶段因 `validate_unique_field_names` 失败

### Requirement: structural preload MUST reuse the same demand-YAML parse settings as runtime entrypoints
workflow structural preload 会解析 demand YAML，因此系统 MUST 复用与 runtime entrypoints 一致的解析设置（至少包含 template 预编译的 `rendered_yaml_max_len` 与 `allowed_yaml_roots`），避免“preload 与 runtime compile 对同一 demand YAML 得出不同结论”的漂移。

#### Scenario: rendered_yaml_max_len is enforced during structural preload
- **GIVEN** 用户调用 workflow 入口并提供 `template_vars`
- **AND** 用户显式设置一个很小的 `rendered_yaml_max_len`
- **WHEN** structural preload 解析某个包含模板渲染的 demand YAML
- **THEN** 若渲染后 YAML 文本超过该上限，系统 MUST 在 structural preload 阶段 fail-fast

### Requirement: effective options/resources merge MUST be the earliest policy-aware boundary for inferable diagnostics
系统 MUST 将 overrides、workflow resources overlay 与 per-run patch 合并为 per-run effective options/resources，并将该合并结果作为 inferable runtime-only diagnostics 的最早输入边界：

- pipeline MUST 在 preflight 前完成 effective merge
- preflight MUST 仅基于 effective merge 口径决定是否触发某个 inferable check

#### Scenario: per-run patches can disable inferable diagnostics before preflight
- **GIVEN** workflow run A 的 demand fields 存在 duplicate effective field display names
- **AND** `run_options_patches_by_run_id["A"].demand_diagnostics.validate_unique_field_names=false`
- **WHEN** 系统执行到 preflight 阶段
- **THEN** 系统 MUST 将该 run 的 effective policy 视为关闭
- **AND** 系统 MUST NOT 因该诊断在 preflight 阶段失败

### Requirement: inferable diagnostics trigger conditions MUST be evaluated using effective outputs/resources (not raw YAML)
系统 MUST 以 effective outputs/resources 的口径来判断 inferable runtime-only diagnostics 是否触发（不得按原始 YAML 口径抢跑），否则会出现 override 后不再冲突/反之的误报或漏报。

#### Scenario: outputs override can disable the duplicate-name trigger
- **GIVEN** 某个 demand fields 存在 duplicate effective field display names
- **AND** 该 demand 的原始 YAML outputs 会写入 `header_fields_output_by=name` 的 header
- **WHEN** 用户通过 runtime overrides 将 effective outputs 调整为“不写 `header_fields_output_by=name` 的 header”
- **THEN** preflight MUST 认为该检查不触发
- **AND** preflight MUST NOT 因 duplicate names 失败

#### Scenario: outputs override can enable the duplicate-name trigger
- **GIVEN** 某个 demand fields 存在 duplicate effective field display names
- **AND** 该 demand 的原始 YAML outputs 不会写入 `header_fields_output_by=name` 的 header
- **WHEN** 用户通过 runtime overrides 将 effective outputs 调整为“会写 `header_fields_output_by=name` 的 header”
- **THEN** preflight MUST 认为该检查触发
- **AND** preflight MUST fail-fast 抛出 duplicate-name 错误

### Requirement: preflight MUST be deterministic and fail-fast on the first error
为保证可维护与可调试，系统 MUST 以确定性顺序执行 preflight，并在发现第一个错误时立即中止：

- runs MUST 按 workflow 声明顺序（decl_order）执行
- 每个 run 的 checks MUST 按 registry 顺序执行
- 遇到第一个错误 MUST 立即 raise（不得聚合多个 run 的错误）

#### Scenario: first failing run stops preflight immediately
- **GIVEN** workflow 存在两个 runs，且按 decl_order 都会触发同一个 preflight 错误
- **WHEN** 系统执行 preflight
- **THEN** 系统 MUST 抛出与第一个 run 对应的错误
- **AND** MUST 不再继续执行后续 run 的 preflight

### Requirement: preflight and runtime compile MUST share a SSOT helper for effective outputs/resources trigger semantics
为避免 drift，系统 MUST 将 effective outputs/resources 的关键触发判定（例如是否会写 `header_fields_output_by=name` 的 header）收敛为单一 SSOT helper，并由：
- workflow preflight 使用
- demand runtime compile（或其 diagnostics runner）使用

#### Scenario: trigger semantics behave identically across preflight and runtime compile
- **GIVEN** 同一份 demand 结构与同一份 effective outputs/resources
- **WHEN** 系统在 preflight 与 runtime compile 两个边界分别判断是否触发某个 inferable check
- **THEN** 两处的触发判定 MUST 一致（不得出现一处触发而另一处不触发的 drift）
