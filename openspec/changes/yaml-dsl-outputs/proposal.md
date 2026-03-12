## Why

业务报表迁移到 Scalim YAML DSL 后,最常见的交付形态并不是“单文件/单输出”,而是:

- **同一份明细宽表分发多 sheet**(按 channel/业务线/订单类型等过滤)
- **在同一次运行中派生汇总 sheet**(group_by + metrics,用于对拍与交付)
- **meta/audit/fingerprint 等对拍友好产物**可一键开启

当前 Scalim 的执行层已实现:

- `output-composition`(多输出目标 + workbook 多 sheet + failure_policy + meta/audit)
- `derived-outputs`(增量聚合 + finalize 输出)

但 YAML authoring surface 仍是单输出模型(`output`),导致业务必须写 Python glue:

- 需要自定义 sink 或手拼 `OutputCompositionSpec`
- 多 sheet 的 where/predicate 只能写 Python callable
- 同类报表的“分发/汇总编排”无法在 YAML 中复用与沉淀

提供了一个最小脱敏可运行样例用于对齐边界:
`openspec/changes/yaml-dsl-outputs/acceptance/mvp_demo/README.md`
其中 baseline 目前用“最薄 Python sink”兜住 multi-sheet 分发,正是本 change 要消灭的 glue.

## What Changes

- 为 demand YAML 增加“多输出编排”入口,把 `output-composition/derived-outputs` 暴露为 YAML authoring surface:
  - 支持声明多个 outputs,并写入同一 workbook 的多 sheet
  - 支持 output 之间的 `from` 复用(继承字段集合/容器配置),并通过 `where` 过滤分发
  - 支持在同一份明细流上声明派生汇总(`aggregate`)并写入汇总 sheet
  - 支持一键启用 meta/audit/fingerprint 等对拍友好标准产物
- `where`/过滤表达式:
  - 使用安全表达式引擎(与 derived compute 同一类约束),拒绝任意导入执行
  - 编译期静态分析其依赖字段,把依赖显式注入到执行层(required fields),避免“过滤字段未在 layout 中导致取值为 None”的隐式口径偏差
- 输出容器与兼容选项:
  - workbook container 支持 `allow_formulas`(保持 legacy 报表行为)与 `write_lock`(并发写护栏)
  - failure_policy 与 error_message 脱敏策略沿用 `output-composition` 既有语义,并可在 YAML 显式配置

## Capabilities

### New Capabilities
- `yaml-dsl-outputs`: 在 demand YAML 中声明多 sheet 分发与派生汇总,把报表编排从 Python glue 下沉到可复用 YAML.

### Modified Capabilities
- `output-composition`: 增加 YAML 侧装配入口(不改变执行语义).
- `derived-outputs`: 增加 YAML 侧装配入口(不改变执行语义).
- `yaml-dsl-schema`: schema 支持 outputs 语法与 where/aggregate 结构.

## Impact

- 受影响模块(预期):
  - `src/scalim/dsl/by_yaml/schema_dsl/**` + schema 生成物
  - `src/scalim/dsl/by_yaml/config_parsing/validator.py`(语义校验: 引用/依赖/冲突诊断)
  - `src/scalim/dsl/by_yaml/runtime/**`(编译期: outputs -> OutputCompositionSpec 装配)
  - `src/scalim/execution/output_composition.py`(可能需要补齐 derived/predicate 适配点)
- 测试/验收:
  - 将 `mvp_demo` 的三块需求表达转为本仓 fixtures/回归用例(脱敏),覆盖:
    - 多 sheet where 分发确定性
    - 派生汇总写入 workbook
    - meta/audit/fingerprint 开关与输出统计
  - canonical demo 必须升级覆盖新语义(`notebooks/.../ecommerce_report.yaml`).
