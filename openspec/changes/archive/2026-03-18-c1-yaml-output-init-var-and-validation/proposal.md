## Why

下游在 Scalim YAML DSL 实战(客服业绩统计报表 `cus_collect_infos`)中暴露出多个“配置可写但结果不可信”的问题:

- `value_cast: str/int` 对 `None` 的处理不符合直觉,会把“无值”变成“有值”(字符串 `"None"` 或抛 TypeError),进一步导致 `compute` 表达式的 `falsy` 判断失效与运行时异常。
- `{$init_var: ...}` 已是 loader params 模板的稳定能力,但在 `outputs.*.container.path` 中目前会被当成普通 dict `str()` 化,最终导致 sink 写入到无效路径;同时 `run_ir` 会吞掉 `sink.close()` 异常,出现 **run() 返回成功但文件未写出** 的静默失败。
- `PROJECT_CLI_NAME yaml-dsl validate` 当前默认不启用 JSONSchema 校验且默认非 strict unknown-fields,使上述配置错误更难在开发/CI 阶段被提前发现。

这些问题的共同点是: 用户看到“validate 通过 / run 成功”但产物缺失或错误,排障成本高且信任受损,因此需要一个高优先级的修复提案来把行为收敛到更可预期、fail-fast 的标准。

## What Changes

- 修复 `value_cast: str/int` 在值为 `None` 时的语义:
  - `None` MUST 透传为 `None`(不再变成 `"None"`、也不抛异常)。
  - **BREAKING**: 依赖 `"None"` 字符串的下游(若存在)会被改变为 `None`。
- 在 YAML DSL 中显式支持 `{$init_var: <name>}` 注入到 `outputs.*.container.path`:
  - 编译期用调用方提供的 `init_vars[<name>]` 解析并替换为最终路径字符串。
  - 缺失 `init_vars` 或缺失 key MUST fail-fast 且报出明确配置路径。
- 更新 `demand.gen.json` 生成规则: `outputs.*.container.path` 的 schema 支持 `string | {$init_var: string}`(oneOf),消除 YAML LSP 类型报错并与运行时能力一致。
- 调整 CLI 校验默认策略(开箱即用、默认严格、最少选项):
  - `PROJECT_CLI_NAME yaml-dsl validate` 默认 strict unknown-fields(不再需要 `--strict`)。
  - `validate` 仍以内部语义校验为主,但会尽可能尝试 JSONSchema 校验:
    - 未安装 `jsonschema` 或 schema 校验非预期失败时: 输出 warning,继续内部校验与 unknown-fields 检查。
  - **BREAKING**: `yaml-dsl validate --strict`(以及可能的 `schema validate --strict`) 将被移除/废弃,以“默认即严格”为唯一入口。
- 修复 `run_ir` 对 `sink.close()` 异常的处理:
  - 若 `engine.run()` 成功完成,`sink.close()` 失败 MUST 使 `run_ir/run()` 失败(这是文件输出成功的真实标准)。
  - 若 `engine.run()` 已抛异常,`sink.close()` 失败 SHALL 被 suppress(可记录日志)以避免覆盖原异常。

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `field-compute`: 明确 `value_cast: str/int` 对 `None` 的语义为透传 `None`(对齐 SQL `CAST(NULL AS ...) -> NULL`)。
- `yaml-runtime-vars`: 扩展 `{$init_var: <name>}` 的解析范围,新增 `outputs.*.container.path` 作为受支持位置(编译期解析;缺失 fail-fast)。
- `yaml-dsl-schema`: 生成的 JSON Schema 覆盖 `outputs.*.container.path` 的 `{$init_var: ...}` 语法,并提供对应 hover/示例。
- `yaml-dsl-cli-validation`: `yaml-dsl validate` 默认严格且尽可能使用 JSONSchema;缺依赖/非预期失败以 warning 形式呈现而不中断内部校验。
- `output-mode-api`: 明确 run 成功路径下 `sink.close()` 异常的传播规则,避免“成功但未落盘”的静默失败。

## Impact

- 影响运行时行为:
  - `value_cast` 在 `None` 行为上变更(潜在 breaking)。
  - `run()`/`run_ir()` 可能在输出落盘失败时返回失败(把隐藏问题显式化)。
- 影响 YAML authoring surface:
  - `outputs.*.container.path` 新增可用写法 `{$init_var: <name>}`;schema/validator/运行时行为对齐。
- 影响 CLI:
  - `yaml-dsl validate` 默认严格;并在可用时执行 JSONSchema 校验,缺依赖会产生 warning。
- 影响文档与技能:
  - 需在 `docs/doc/yaml-dsl/` 与 `artifacts/skills/scalim-yaml-dsl/` 明确 `$init_var/$keys/$rows` 的使用范围约束,并同步更新 CLI 示例(默认 strict,不再需要 `--strict`)。
- 需要同步修改的代码/测试大致范围:
  - `src/scalim/dsl/by_yaml/runtime/_internal/conversion_lookup.py` (`cast_str/cast_int`)
  - `src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py` (生成 schema oneOf)
  - `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py` + runtime output composition 编译链路(解析/编译期解析 init_var)
  - `src/scalim/execution/run_ir.py`(close 异常语义)
  - `src/scalim/cli/yaml_dsl.py` + `tests/test_yaml_dsl_cli_output.py`(validate 默认严格与 jsonschema best-effort)
