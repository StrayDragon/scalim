---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate runtime-guardrails --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "runtime-guardrails"
purpose: "定义运行期 guardrails 配置与执行契约,用于对 loader/relations/compute 等环节的契约违规、数据质量问题与异常处理提供可配置的 quiet/fast_fail 行为,并通过现有错误事件通道进行可观测记录."
requirements[7]{req_id,title,statement}:
  r1,Guardrails 配置与默认行为,"系统 SHALL 提供可选的 guardrails 配置用于运行期护栏控制;默认 `enabled=false` 时不得改变现有执行行为. 系统 SHALL 支持 `mode: quiet|fast_fail`(默认 fast_fail) 并在 `fast_fail` 时对护栏违规抛出终止异常. guardrails 配置 SHALL 按职责分层,包含 `loader`/`relations`/`compute` 子配置;关键字段缺失检查配置位于 `guardrails.loader.required_fields`."
  r2,runtime guardrails MUST NOT swallow callable preflight failures,"系统 MUST 将 callable preflight 失败定义为配置/编译错误边界: - callable preflight 失败 MUST 在 engine 执行前 fail-fast 抛出（例如 demand compile 或 workflow preflight 阶段）。 - 运行期 guardrails（包括 `guardrails.mode=quiet` 与 `guardrails.compute.on_error`）MUST NOT 将此类错误降级为 `None` 或静默记录后继续执行。"
  r3,quiet 模式违规记录,"当 guardrails 启用且 `mode=quiet` 时,系统 MUST 在发生违规时记录违规信息,但不得终止 pipeline. 系统 MUST 通过现有 Hook/Observer 错误通道记录该违规(例如 ErrorEvent/Hook.on_error),并在 context 中标记 `guardrail=true` 与 `mode=quiet`(以及可选的 severity 标记). 实现 MAY 在未注册任何错误订阅时短路该记录动作(允许无输出),以保持\"静默\"与性能."
  r4,Loader 结果结构护栏,"系统 SHALL 在 `guardrails.loader.validate_result=true` 时在 loader 返回结果后进行结构校验: - loader 结果 MUST 为 Mapping(row_id -> row_data),不要求必须是 `dict`. - row_data MUST 为 RowLike(见下方字段提取语义). 当 `guardrails.loader.validate_result=true` 且发生**契约违规**(例如 loader 返回非 Mapping)时,系统 MUST 终止 pipeline(等价 fast_fail),不得被 `mode=quiet` 覆盖."
  r5,RowLike 字段提取语义(无歧义优先级),"系统 SHALL 将 `row_data` 视为 RowLike,并按以下固定优先级提取 `data_key` 对应的值(优先级必须写死以避免歧义): 1. 若 `row_data` 为 Mapping,系统 MUST 使用 `row_data.get(data_key)` 提取字段值. 2. 否则,系统 MUST 尝试 `object.__getattribute__(row_data, data_key)` 提取字段值;若抛出 AttributeError 则视为该属性不存在并进入下一步. 3. 否则,若 `row_data` 支持 `__getitem__`,系统 MUST 使用 `row_data[data_key]` 提取字段值. 4. 否则,系统 MUST 将该字段视为缺失(值为 None)."
  r6,关键字段缺失护栏,"系统 SHALL 支持在 `guardrails.loader.required_fields` 中声明关键字段列表(任意 field_id),对这些字段的缺失/None 进行检查. `guardrails.loader.required_fields` 中的条目 SHALL 支持 `field_id` 字符串或 YAML alias(指向已定义字段对象);当为 alias 时系统 MUST 将其解析为外部 key 对应的 `field_id`. 关键字段检查仅作用于显式配置的字段,不自动覆盖全部 required_fields. 当 guardrails 启用且关键字段缺失时,系统 MUST 按 guardrails.mode 处理."
  r7,字段 extractor/value_cast/transform 异常护栏,"系统 SHALL 在 guardrails 启用时捕获源字段的 extractor/value_cast/transform/value_formatter 等转换异常,并支持 fail-fast 策略以避免中途 batch 半程失败."
scenarios[18]{req_id,id,given,when,then}:
  r1,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r1,默认关闭,"",未提供 guardrails 配置,"执行行为与当前版本一致,不增加额外失败条件"
  r1,"fast-fail-模式终止","",guardrails.enabled=true 且 guardrails.mode=fast_fail,任一护栏违规应终止 pipeline 并报告违规类型
  r2,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r2,"compute-quiet-mode-does-not-convert-preflight-failure-to-non",`guardrails.enabled=true` 且 `guardrails.mode=quiet`,调用方执行 demand `run`,系统 MUST 在运行前失败并抛出编译错误
  r3,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r3,"quiet-模式记录并继续","",guardrails.enabled=true 且 guardrails.mode=quiet 且发生任意护栏违规,"pipeline 继续执行,并记录一次可观测的违规信息(不要求逐行输出)"
  r4,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r4,"loader-返回非-mapping","",loader 返回 list/tuple/None 等非 Mapping,触发 guardrail 契约违规并终止 pipeline
  r5,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r5,"row-data-为非-dict-的-mapping-也可提取字段-修复静默-none","",loader 返回的 row_data 为非 dict 的 Mapping(如 UserDict/MappingProxyType/自定义 Mapping),"字段提取与 dict 等价,不得因 Mapping 类型而走属性访问并静默返回 None"
  r5,"row-data-为属性对象","",row_data 为 dataclass 实例/SimpleNamespace/namedtuple 等可用属性访问提取字段的对象,系统可通过属性访问取得字段值
  r5,"row-data-为-duck-typed-getitem-对象","","row_data 不是 Mapping 且无同名属性,但支持 `__getitem__`(如某些第三方行对象)","系统可通过 `row_data[data_key]` 取得字段值"
  r6,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r6,关键字段缺失,guardrails.loader.required_fields 包含 `order_id`,加载结果中 `order_id` 为 None 或不存在,触发 guardrail 违规并按配置处理
  r6,"required-fields-支持-yaml-alias",YAML 中 `main_source.fields.customer_id` 被定义为 anchor 且 guardrails.loader.required_fields 引用该 alias,解析配置并运行,系统将 alias 解析为 `customer_id` 并按关键字段缺失规则进行检查
  r7,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r7,"转换异常触发-guardrail",guardrails 启用且某个字段的 value_cast 抛出异常,loader 尝试提取并转换该字段,系统 MUST 捕获异常并按 guardrails.mode 处理
```
