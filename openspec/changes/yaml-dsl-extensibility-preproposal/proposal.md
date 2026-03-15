## Why

当前 `YAML DSL` 的用户经常需要“临时加一点能力/行为”来做快速验证(自定义输出、扩展聚合、注入诊断/观测、调整编译/执行策略等)。但很多能力一旦落在框架内部,就会把用户绑定到发布周期:用户需要等待新版本、升级、再落地使用,导致“框架已支持”与“用户可用”的时间差过大。

因此需要一套 **YAML-first 的显式切入面**:用户仍以写 YAML 为主,但可以通过受控的 Python 扩展(函数/类继承/自定义 sink/hook/observer 等)来改变行为,把“快速试验/临时能力”尽可能从框架发版中解耦出来。

> 本 change 是“预提案(pre-proposal)”:用于评审与拆分后续具体 changes. 该提案覆盖完整的扩展性方案与边界,实现可以分阶段推进。

## What Changes

- 在 YAML DSL 中新增可选顶层块 `extensions`,作为“可信输入(trusted YAML)”场景下的对外扩展入口,并**同时支持三种扩展形态**:
  - **BUNDLE**: `extensions.bundles` 声明 bundle factories,每个 bundle 返回一组扩展贡献(注册函数/注册格式/注入组件/提供变换器/提供分析器等)。
  - **ANALYZE**: `extensions.analyze` 声明 analyzers(只读分析),用于输出额外的校验/诊断/建议/元信息,支持 CLI/IDE/CI 消费。
  - **Direct config**: 在 `extensions.compute/components/outputs/aggregates/transform` 等键下直接声明常见扩展(无需写 bundle)。
- 为扩展契约引入两个“收敛点”(SSOT):
  - `extensions.api` 作为版本号(缺省视为 1;未知版本 fail-fast),保证扩展语义可演进且可对拍
  - `ExtensionHost` 作为编译期唯一扩展产物(合并 direct + bundles),供 validator/parser/compiler/executor/CLI 共享,避免漂移
- 定义并落盘一组完整且可拆分的扩展契约(面向 Python 代码),覆盖:
  - **表达式扩展**: 为 `compute/where` 的安全表达式引擎注册额外函数名与实现
  - **装配扩展**: 从 YAML 装配额外 `Observer`/`IExecutionHook` 组件(无需改 driver)
  - **输出扩展**: 输出 format/sink 的 registry 可由扩展注入,并允许 `outputs[*].container.type` 使用自定义 format id(可携带 `options`)
  - **派生汇总扩展**: `outputs[*].aggregate` 支持自定义 kind/ref,由扩展返回 `IDerivedAggregationSpec/IRowAggregator` 实现实验性聚合
  - **编译期扩展**: raw-config → config/IR/request 的可选变换器(transformers),用于宏/默认值注入/装配覆盖等
  - **分析期扩展**: analyzers 可在 compile/validate 阶段产出结构化 issues 与摘要(用于 `yaml-dsl validate` 与可选 `yaml-dsl analyze`)
- 明确一条 extensions-aware 的编译管线:
  - raw transformers 必须发生在核心 validator 之前(宏/默认值注入与校验一致)
  - compute/where 的依赖推导必须忽略函数名(否则扩展函数会被误判为字段依赖)
  - custom aggregate 的 `required_fields()` 必须在字段裁剪前注入 required 字段闭包(避免 composed outputs 缺字段)
- 形成“可审计/可回滚”的扩展运行边界:
  - 扩展引用统一走 allowlist resolver(显式授权)
  - 扩展贡献合并具备确定性顺序与冲突策略(可配置)
  - 错误包含 `yaml_path/ref/stage` 等上下文,便于排障与回归对拍

## Capabilities

### New Capabilities
- `yaml-dsl-extensions`: 为可信 YAML 场景提供显式扩展入口与完整扩展契约(BUNDLE/ANALYZE/direct config),允许用户通过 Python 扩展改变编译/执行装配与输出/聚合行为,以降低对框架发版的依赖。

### Modified Capabilities
- `yaml-dsl-schema`: schema 需要允许并描述顶层 `extensions`(含 bundles/analyze/direct config),并允许 `extensions.*.options` 类自由配置容器,避免扩展每次都要求框架同步发版 schema。
- `yaml-dsl-cli-validation`: `yaml-dsl validate`/`schema validate` 需要能承载并展示扩展 analyzers 产出的 issues(并可选提供 `yaml-dsl analyze` 的结构化输出)。
- `output-composition`: composed outputs 的 sink 创建与 container/type 能力需可被扩展 registry 覆盖/扩展(保持内置 csv/excel 兼容)。
- `derived-outputs`: 需要明确并支持“自定义聚合器”从 YAML 扩展装配进入 derived outputs 的边界与并发约束。

## Impact

- YAML authoring surface:
  - 新增 `extensions` 顶层块(可选;不影响无扩展的现有 YAML)。
- 预期影响代码面(后续拆分实现时):
  - 配置加载/校验/解析: `src/scalim/dsl/by_yaml/config_parsing/loader.py`, `src/scalim/dsl/by_yaml/config_parsing/validator.py`
  - compute 依赖推导/安全引擎: `src/scalim/dsl/by_yaml/config_parsing/security.py`
  - 编译链路装配: `src/scalim/dsl/by_yaml/runtime/compiler.py`, `src/scalim/dsl/by_yaml/runtime/conversion.py`
  - outputs/where/aggregate 编译: `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`, `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`
  - 执行装配与输出: `src/scalim/execution/run_ir.py`, `src/scalim/execution/output_composition.py`
  - CLI 校验与诊断输出: `src/scalim/cli/yaml_dsl.py`
  - schema 生成与镜像(若落地): `src/scalim/dsl/by_yaml/schema_dsl/*`, `scripts/gen-yaml-dsl-schema.py`, 以及 `frontend/` schema 镜像同步门禁(见 `_X/03-frontends.md`)。
