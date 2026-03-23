## Why

`src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py` 中的 outputs 解析逻辑存在典型的“巨型函数 + 多职责耦合”问题（例如 `_parse_outputs` 带有复杂度豁免），使得：

- 输出配置（container/fields/aggregate/from 继承）之间的规则难以局部修改与验证
- 任何小需求都可能触发大范围改动与回归风险
- 很难为关键分支补齐细粒度单测（因为逻辑嵌套深、状态隐式通过局部变量传递）

同时该模块还承担了枚举常量、DAG 解析、compute/call_by 安全解析等职责，长期会继续膨胀。

## What Changes

- 将 outputs 解析拆分为可组合的阶段（保持对外行为不变）
  - Phase 1：结构解析（raw mapping → typed config，做类型检查与路径错误定位）
  - Phase 2：引用/继承解析（`outputs.*.from` 的合并、cycle detection、默认继承规则）
  - Phase 3：语义校验（container/fields/aggregate 的互斥与约束、producer key 合法性、依赖提取）
  - Phase 4：衍生信息产出（required_field_ids 计算、输出目标 canonicalization）
- 提取小型 helper/类
  - 例如 `OutputTargetIndex/Resolver`（负责 name 唯一性、from 合并与 cycle）
  - 例如 `AggregateFieldParser`（负责 aggregate.fields 的 producer_key 分发与依赖提取）
- 为拆分后的阶段补齐单元测试
  - 每个 phase 的最小 fixture（尤其是 from 继承、aggregate DAG、compute/call_by 依赖提取、错误路径定位）
  - 将历史回归用例固化为测试，作为 refactor 护栏

## Capabilities

### New Capabilities
- `outputs-parser-staged-design`: 定义 outputs 解析的阶段化架构与可测试边界（每个 phase 的输入/输出、以及必须覆盖的回归场景）。

### Modified Capabilities
（无；目标是重构实现，不改变 YAML authoring surface 与语义）

## Impact

- 受影响代码：
  - `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`（主拆分）
  - 可能引入新的 `parsers/outputs_*` 子模块以承载拆分后的职责
  - `tests/`（新增/加强针对 outputs 解析的单元测试）
- 预期收益：
  - 降低复杂度与改动半径，提升可维护性与可测试性；为后续扩展 outputs/aggregate 能力提供更安全的演进基础
