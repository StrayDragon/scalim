## Context

本变更聚焦三个用户侧痛点:

1. 字段 `value_cast: str/int` 对 `None` 的行为不符合直觉,会把“无值”变成“有值”(或异常),进而影响 `compute` 表达式中的 `falsy` 判断与运行稳定性。
2. `{$init_var: ...}` 在 loader params 模板中是既有能力,但在 `outputs.*.container.path` 中目前会被当成普通 dict `str()` 化,导致 sink 使用无效路径;并且 `run_ir` 目前无条件 suppress `sink.close()` 异常,出现静默失败。
3. CLI 校验默认非 strict 且默认不启用 JSONSchema,使上述问题更难被开发/CI 提前发现。

约束与边界:

- 运行时代码(`src/scalim/`)必须兼容 Python 3.6。
- `src/scalim/dsl/by_yaml/schema/demand.gen.json` 为生成物,禁止手改;SSOT 在 `src/scalim/dsl/by_yaml/schema_dsl/`。
- `jsonschema` 是可选依赖;缺失时应保持可用性,但需要可诊断的 warning。

## Goals / Non-Goals

**Goals:**

- `value_cast: str/int` 在 `None` 值时透传 `None`,避免 `"None"` 或异常破坏下游表达式/逻辑。
- 支持 `{$init_var: <name>}` 在 `outputs.*.container.path` 中的注入与编译期解析:
  - 解析后必须得到非空字符串路径
  - 缺失 init var 需 fail-fast 且报出明确配置路径
- 消除“run 成功但文件没写出”的静默失败:
  - `engine.run()` 成功时,`sink.close()` 失败必须让 `run()` 失败
  - `engine.run()` 异常时,close 仍 best-effort,不覆盖原异常
- `PROJECT_CLI_NAME yaml-dsl validate` 默认严格(未知字段=错误)且尽可能执行 JSONSchema 校验;缺依赖/非预期 schema 失败给 warning,但不影响内部语义校验输出。

**Non-Goals:**

- 不引入通用字符串模板/子串替换(例如 `"$init_var.xxx"` 形式)到 path 等字段;仅支持结构化指令节点 `{$init_var: <name>}`。
- 不在本变更中把 `{$init_var: ...}` 扩展到 YAML DSL 的所有 string 字段(范围先收敛到 `outputs.*.container.path` 及其派生使用点)。
- 不新增/堆叠大量 CLI 开关;以“默认开箱即用 + 默认严格”为主。

## Decisions

### Decision 1: `value_cast: str/int` 的 `None` 语义统一为透传

选择:
- 在 `value_cast` 的具体转换函数里对 `None` 做短路,返回 `None`。

原因:
- `None` 在 DSL 语义中代表缺失/无值,应作为有意义的状态被保留。
- 对齐 SQL `CAST(NULL AS ...) -> NULL` 的用户预期。
- 相比“抛异常再由 guardrails 兜底”,短路更稳定且避免将 `None` 错误转为 truthy 值。

备选:
- 维持现状,建议用户在 compute 表达式里额外判断 `"None"` 字符串 → 排除:把实现问题推给用户且不可读。

### Decision 2: `outputs.*.container.path` 支持 `{$init_var: <name>}` 并在编译期解析

选择:
- 在 YAML 解析阶段允许 `path` 为:
  - 非空字符串
  - 形如 `{"$init_var": "<name>"}` 的 mapping(允许 inline/block 写法)
- 在“构建 `OutputCompositionSpec`”阶段(即 `compile_output_composition_from_yaml(...)`)引入 `init_vars` 参数并解析该指令节点:
  - 缺失 `init_vars` 或缺失 key → 抛出带配置路径的错误
  - 解析结果使用 `str(value).strip()` 归一化并要求非空
- 执行层(Excel/CSV sinks)不理解/不接触该指令节点;拿到的一律是最终字符串路径。

原因:
- `init_vars` 是运行时入口参数,不应强行注入到纯 YAML loader(`YamlDemandLoader`)API;更适合在 runtime compiler/build-request 阶段处理。
- 保持“指令节点在执行前被消解”的契约: execution 层只处理 literal 值。

备选:
- 在 YAML loader 里直接解析并要求 init_vars → 排除: loader 不具备 init_vars 上下文,会扩大 API 面并影响复用/测试。
- 不支持该语法而是明确报错 → 可作为 fallback,但本变更选择支持以减少下游 glue code。

### Decision 3: Schema(编辑器/Schema-only)与运行时语义对齐

选择:
- 修改 schema SSOT(`schema_dsl/models/outputs.py`)里 `OutputContainerConfig.path` 的 `schema_meta.schema` 为 `oneOf`:
  - string(minLength=1)
  - object: `{"$init_var": string}`, required `"$init_var"`, `additionalProperties=false`
- `demand.gen.json` 通过既有生成脚本再生,并由 drift test 护航。

原因:
- 让 YAML Language Server 认识到这是“合法写法”,避免编辑器红线噪音。
- schema-only 校验能提前发现指令节点形态错误(多余 key/空值等)。

### Decision 4: CLI validate 默认严格 + best-effort JSONSchema

选择:
- 移除 `yaml-dsl validate --strict` 选项,将未知字段校验视为默认行为(默认 strict)。
- `yaml-dsl validate` 在内部语义校验之外,尽可能执行 JSONSchema:
  - `jsonschema` 缺失/不可用/非预期异常 → 输出 warning,但命令仍返回“基于内部语义校验”的结论。
- 调整 validate 的 `ok` 判定: warnings 不应因为“默认严格”而导致失败;严格模式通过“把 unknown-fields 变成 errors”体现即可。

原因:
- 让命令在最小依赖环境也“开箱即用”,但依然尽可能提供更强校验与诊断。
- 默认 strict 简化心智模型,减少脚本/CI 漏配。

### Decision 5: `run_ir` 的 close 异常传播语义

选择:
- `engine.run()` 成功时:
  - `sink.close()` 异常必须传播(让 run() 失败),因为文件输出成功以 close 为准。
- `engine.run()` 已抛异常时:
  - best-effort close;close 异常不覆盖原异常(可记录日志)。

原因:
- 解决“run 成功但文件没写出”的信任问题。
- 避免异常链被 close 异常覆盖导致排障困难。

## Risks / Trade-offs

- [BREAKING] `yaml-dsl validate --strict` 相关脚本会失败 → 通过升级指南/CHANGELOG 提示;新默认即严格,脚本直接去掉该参数即可。
- `init_vars` 值若不是字符串/Path,最终仍会被 `str()` → 用户可能传入意外对象导致路径不可用 → 通过 `.strip()` + 非空校验与明确错误信息缓解。
- `sink.close()` 在成功路径抛错会让 run() 失败,可能暴露此前被吞掉的输出问题 → 属于预期,但需在 release notes 强调这是“修复静默失败”。

