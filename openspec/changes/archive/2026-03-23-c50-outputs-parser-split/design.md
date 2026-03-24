## Context

`src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py` 当前承担 outputs 解析的多种职责，并且 `_parse_outputs` 存在复杂度豁免（`# noqa: C901/PLR0915/...`），导致：

- 规则修改难以局部验证（from 继承、aggregate 语义校验、required fields 推导等交织在一起）
- 错误路径定位与诊断格式难以保持稳定（局部变量传递隐式状态）
- 单元测试难以按分支覆盖（缺少“可注入/可分阶段验证”的纯函数边界）

As-Is 主要阶段已经在一个函数里隐式存在：

1. 结构解析：把 `outputs` list item 解析为 `OutputTargetConfig`
2. from 解析：基于 name 建索引并做继承合并 + cycle detection
3. 语义校验：跨 outputs 的互斥/约束/字段合法性校验
4. 衍生信息：计算 required_field_ids

约束：

- 运行时需兼容 Python 3.6；by_yaml 内倾向相对导入，避免引入新的循环依赖。
- 本变更为重构：目标是不改变 YAML authoring surface 与语义；如发现历史行为有歧义，必须通过测试显式固化。
- 需要与其它 changes 的 SSOT 一致（例如 producer keys SSOT、ordered-unique SSOT）。
  - 本设计假设 `ordered-unique-ssot` 与 `output-aggregate-producer-keys-ssot` 已完成；若未完成，应先完成 SSOT 再做 staged 拆分（否则会扩大改动半径与漂移风险）。

## Goals / Non-Goals

**Goals:**

- 将 outputs 解析按职责拆分为可组合阶段（staged parsing），并确保每阶段可被单元测试覆盖。
- 把复杂度豁免收敛到极少数 glue 层，尽量让核心逻辑变成小函数/小类（可读、可测、可 review）。
- 固化关键错误语义：
  - from cycle 的检测必须确定性且错误信息包含 output name（或等价诊断）
  - unknown output/from 的错误必须可定位（包含 name）

**Non-Goals:**

- 不改变输出语义、默认继承策略、或 aggregate DAG/依赖提取规则。
- 不在本变更内解决其它模块的 SSOT 重复（单独 change 负责）。
- 不引入新的对外 API（仅内部重构；对外入口与 import 路径保持稳定）。

## Decisions

### 1) 分层拆分：保留现有对外入口，内部引入 staged functions

**决策：**

- 对外仍保留 `ParserOutputsMixin._parse_outputs(...)`（调用点不变）。
- 在同文件或子模块中引入阶段化纯函数（建议放到同目录 `parsers/outputs_*` 子模块以降低单文件密度）：
  1. `parse_output_targets_base(...) -> List[OutputTargetConfig]`（结构解析；主要复用 `_parse_output_target`，并把局部 helper 进一步拆小）
  2. `resolve_output_from_inheritance(base_targets) -> List[OutputTargetConfig]`（name 索引 + from 合并 + cycle detection）
  3. `validate_outputs_semantics(resolved_targets, ...) -> None`（语义校验）
  4. `collect_required_field_ids(resolved_targets) -> Optional[List[str]]`（衍生信息产出）

**理由：**

- 最大化复用现有 dataclass 模型（`OutputTargetConfig` 等），避免引入新的中间数据模型导致迁移成本飙升。
- 分阶段后能为每个阶段建立最小 fixture 与单测，不必依赖完整 YAML/完整 validator 才能测试局部规则。

### 2) from 解析的 SSOT：显式 index + resolver（确定性 cycle 检测）

**决策：**

- 把 from 解析从 `_parse_outputs` 内部闭包提取为显式组件（函数或小类）：
  - 构建 `by_name: Dict[str, OutputTargetConfig]` 并在此阶段做 name 校验/重复 name 拒绝
  - DFS 解析 `from` 并做 cycle detection（visiting set），错误信息包含发生 cycle 的 name
  - 合并规则保持现状（container/fields 的继承策略不变）

**备选：**

- 在结构解析阶段就“边 parse 边 resolve from”：会引入前向引用与顺序依赖，增加复杂度与错误歧义。

### 3) 测试策略：以 staged tests 作为重构护栏（不依赖大范围 e2e）

**决策：**

- 为每个阶段新增小型单元测试：
  - Stage 2：from cycle 检测、unknown from、fields 继承缺失等错误分支
  - Stage 3：container/aggregate/fields 互斥与约束（最小 case）
  - Stage 4：required_field_ids 的去重保序与稳定性
- 保留少量 e2e 测试（通过 `YamlDemandLoader` 或 `ConfigValidator`）作为“整体 glue 未破坏”的 smoke。

## Risks / Trade-offs

- [回归风险] 重构可能改变错误消息细节或边界行为 → 缓解：先把现有行为用测试固化（尤其是 from cycle、unknown from、继承规则），再重构实现。
- [文件拆分] 过度拆分可能导致 import 链路变长 → 缓解：拆分只在 `parsers/outputs_*` 内部；对外入口保持稳定；避免跨层依赖。
- [测试成本] 增加大量 staged 测试需要一定工作量 → 缓解：优先覆盖最关键分支（from/aggregate/required fields），其余分支在后续迭代补齐。

## Migration Plan

1. 先新增 staged tests 固化关键行为（从 cycle / unknown from / 继承缺失等）。
2. 引入阶段化函数/小类，并逐步把 `_parse_outputs` 缩减为“调用各阶段”的 glue。
3. 逐步移除复杂度豁免或将其局限在 glue 层。
4. 运行 `just qa` 与 `just openspec-check`。
