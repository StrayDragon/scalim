# derived-outputs Specification

**状态: ⚠️ 实验性**
## Purpose
支持在同一次运行中基于详情行流生成派生输出(增量聚合 + finalize 阶段输出),并定义 IR/Python-only 配置入口、资源护栏与 `adaptive` 并发边界.

## Related Code (as implemented)
- `src/IMPL_ROOT/execution/derived_outputs.py` (内置增量聚合接口与实现)
- `src/IMPL_ROOT/execution/output_composition.py` (派生输出在 Router/close 阶段输出)
- `src/IMPL_ROOT/execution/run_ir.py` (ExecutionRequest.output_composition 装配入口)
## Requirements
### Requirement: 派生输出定义(同步聚合)
系统 SHALL 支持在同一次运行中定义派生输出,派生输出可基于详情数据进行聚合/计算,并在运行结束时输出结果.

#### Scenario: 订单明细 → 供应商利润率
- **WHEN** 详情输出包含订单ID/订单金额/订单利润/供应商ID
- **AND** 派生输出按供应商ID聚合利润率
- **THEN** 系统应生成包含供应商ID与利润率的汇总输出

### Requirement: 增量聚合与批次累计
系统 SHALL 支持派生输出以增量方式累计(按批次或流式),以避免加载全部详情数据.

#### Scenario: 分批 2000 行累计
- **WHEN** 详情数据按批次(每批 2000 行)处理
- **THEN** 派生聚合应跨批次累计并在结束时输出完整结果

#### Scenario: 可合并统计(均值/比率)
- **WHEN** 派生输出需要计算均值或比率(如利润率=利润/金额)
- **THEN** 系统应仅累计必要的分子/分母状态并在结束时输出结果

#### Scenario: Top-K 近似聚合
- **WHEN** 派生输出需要 Top-K 排名且数据量巨大
- **THEN** 系统应允许使用可合并的近似算法并以有限内存完成累计

### Requirement: 派生输出的数据来源选择
系统 SHALL 允许派生输出明确选择其数据来源(例如直接消费运行期事件/批次结果,或基于已落盘的详情输出),以平衡内存与 I/O 成本.

#### Scenario: 列式输出的后置聚合
- **WHEN** 详情输出采用列式或落盘模式
- **THEN** 派生输出可选择在详情落盘后进行聚合

#### Scenario: 事件流增量聚合
- **WHEN** 派生输出选择消费运行期事件或批次结果
- **THEN** 系统应允许在详情写入后立即更新聚合状态而不保留明细

### Requirement: 非增量指标的处理方式
系统 SHALL 支持对不可增量的统计指标提供可行路径,包括可合并近似算法或二阶段后置聚合.

#### Scenario: 需要全量数据的指标
- **WHEN** 指标无法在单批次内增量计算(例如精确分位数)
- **THEN** 系统应允许使用近似算法或选择后置聚合模式完成输出

#### Scenario: 精确分位数后置聚合
- **WHEN** 需要精确分位数且不允许近似
- **THEN** 系统应允许将该指标标记为后置聚合并在详情落盘后计算

### Requirement: 聚合状态资源控制
系统 SHALL 支持派生输出聚合状态的资源控制(如阈值、落盘、降采样),以避免内存过载.

#### Scenario: 聚合键数量过大
- **WHEN** 聚合键数量超过预设上限
- **THEN** 系统应触发既定的资源控制策略并继续主流程

### Requirement: IR/Python 配置入口
系统 SHALL 仅提供 IR/Python 方式配置派生输出,并保持 YAML DSL 不变.

#### Scenario: 仅使用编程方式配置
- **WHEN** 用户通过编程方式定义派生输出
- **THEN** 系统应无需修改 YAML DSL 即可运行

### Requirement: `adaptive` 一致性边界
系统 SHALL 明确 `adaptive` 并发下派生聚合的一致性边界,并在不满足条件时 fail-fast.

#### Scenario: 内置可交换聚合在 adaptive 下可用
- **WHEN** 派生输出仅使用内置可交换/可结合的增量指标(count/sum/min/max/count_true)并在 finalize 阶段单线程输出
- **AND** 运行模式为 `parallel_mode="adaptive"`
- **THEN** 系统应允许派生聚合并确保结果确定性

#### Scenario: 自定义聚合器在 adaptive 下默认拒绝
- **WHEN** 派生输出使用自定义聚合器且未声明支持 `adaptive`
- **AND** 运行模式为 `parallel_mode="adaptive"`
- **THEN** 系统应 fail-fast 并提示切换到 `parallel_mode="seq"`

### Requirement: `max_groups=0`(不设上限)时必须输出明确 warn
当派生聚合输出的 `max_groups=0` 表示“不设上限”时,系统 MUST 输出明确的 warn,提示高基数 group-by 可能导致聚合状态无限增长并拖垮内存.

该 warn MUST 仅作为告警,不得改变结果语义(仍信任用户配置).

#### Scenario: 无上限聚合触发 warn
- **GIVEN** 某个派生输出配置 `max_groups=0`
- **WHEN** 运行开始执行派生聚合
- **THEN** 系统 MUST 输出一次 warn 提示资源耗尽风险并建议设置 `max_groups`

### Requirement: 内置 set 口径聚合原语
系统 SHALL 在 `derived-outputs` 的内置聚合能力中新增 streaming-friendly 的 set 口径原语,用于减少业务侧 Python state 并提升复用性.

系统 MUST 至少支持:
- `count_distinct(field_id=...)`(支持复合 key)
- `dedup_by(key_fields=..., on_conflict=error|first|last)`
- `two_stage_group_by(stage1=..., stage2=...)`

#### Scenario: `count_distinct` 统计 distinct 用户数
- **GIVEN** 详情流包含 `cs_id` 与 `user_id`
- **WHEN** 派生输出按 `cs_id` 分组并对 `user_id` 执行 `count_distinct`
- **THEN** 系统 MUST 输出每个 `cs_id` 的 distinct 用户数且结果确定性

### Requirement: `count_distinct` 复合 key 与缺失值语义
系统 MUST 支持 `count_distinct` 同时接受:
- 单字段 distinct: `count_distinct(field_id=...)`
- 复合 key distinct: `count_distinct(field_ids=(...))`

系统 MUST 明确缺失值语义,并保证对拍友好:
- 当 distinct key 的任一组成字段为 `None` 时,该行 MUST 被忽略(对齐 SQL `COUNT(DISTINCT)` 的 `NULL` 语义).
- 空字符串 `""` MUST 作为普通值参与 distinct.

#### Scenario: 复合 key 的缺失值忽略
- **GIVEN** distinct key 由 `cs_id` 与 `user_id` 组成
- **WHEN** 某行的 `user_id` 为 `None`
- **THEN** 系统 MUST 忽略该行且不计入 distinct 计数

### Requirement: `dedup_by` 冲突策略必须确定且可对拍
系统 MUST 对 `dedup_by` 在同一 key 命中多行时的冲突策略提供显式配置,并保证在相同输入下结果确定性.

#### Scenario: `dedup_by.on_conflict=first`
- **GIVEN** 两行数据具有相同的 dedup key
- **WHEN** 配置 `dedup_by(..., on_conflict=first)`
- **THEN** 系统 MUST 选择稳定的“第一条”并用于后续指标计算

### Requirement: `adaptive` 下的确定性边界(顺序依赖语义 fail-fast)
系统 MUST 明确 `parallel_mode="adaptive"` 下的确定性边界: 任一阶段包含顺序依赖语义时,系统 MUST fail-fast 并提示切换到 `parallel_mode="seq"` 或改用非顺序依赖配置.

系统 MUST 至少包含下列规则:
- `dedup_by.on_conflict=first|last` 属于顺序依赖语义,在 `adaptive` 下 MUST fail-fast.
- `dedup_by.on_conflict=error` 在 `adaptive` 下 MUST 允许(仍保持确定性,且错误信息不得泄露敏感 key 值).

#### Scenario: `adaptive` 下拒绝顺序依赖去重策略
- **WHEN** `parallel_mode="adaptive"` 且 `dedup_by.on_conflict=first`
- **THEN** 系统 MUST fail-fast 并提示切换到 `parallel_mode="seq"`

### Requirement: 两阶段聚合固定 tie-break 与输出顺序
系统 MUST 为 `two_stage_group_by` 的 stage1/stage2 均定义确定性的 tie-break 与输出顺序规则,以避免对拍误报.

#### Scenario: stage1 先按 `user_id` 聚合再按 `cs_id` 汇总
- **WHEN** stage1 按 `user_id` 累计 `pay_order_cnt`
- **AND** stage2 按 `cs_id` 统计 `count_true(pay_order_cnt>=2)`
- **THEN** 系统 MUST 在相同输入下产生相同输出(含顺序)

### Requirement: distinct/去重状态的资源护栏与溢出策略
系统 SHALL 为 set 口径状态提供可配置护栏,用于限制聚合状态规模并提供可对拍诊断信息.

系统 MUST 支持:
- `max_distinct`: distinct key 数上限(0 表示不设上限)
- `on_overflow`: 溢出策略(至少支持 `error|truncate`)

系统 MUST 满足:
- 当 `max_distinct=0` 表示“不设上限”时,系统 MUST 输出一次明确 warn(仅告警,不得改变结果语义).
- 当 `on_overflow=error` 且 distinct key 数超过上限时,系统 MUST fail-fast 并给出可操作错误提示.
- 当 `on_overflow=truncate` 时:
  - 系统 MUST 以确定性方式截断(同一输入下结果可对拍;不得依赖不稳定的输入顺序).
  - 系统 MUST 记录截断发生的结构化审计信息(不得泄露明细 key 值).

#### Scenario: distinct 护栏不设上限触发 warn
- **GIVEN** 用户将 distinct 护栏配置为不设上限(例如 `max_distinct=0`)
- **WHEN** 运行开始执行 set 口径聚合
- **THEN** 系统 MUST 输出一次 warn 提示高基数风险,但不得改变结果语义

### Requirement: 最小条件计数原语(支持 `repeat_paid_users`)
系统 MUST 提供至少一种“可对拍且可指纹化”的条件计数能力,用于覆盖 `repeat_paid_users` 等常见口径.

系统 MUST 至少支持:
- `count_true_gte(field_id, threshold)`(当 `field_id` 的数值 >= threshold 时计数 +1)

#### Scenario: `count_true_gte` 阈值计数
- **GIVEN** 某行 `pay_order_cnt=2`
- **WHEN** 指标配置为 `count_true_gte(field_id="pay_order_cnt", threshold=2)`
- **THEN** 系统 MUST 对该行计数 +1

### Requirement: meta/audit 的稳定指纹与结构化审计
系统 MUST 为每个 derived target 生成稳定聚合指纹(不包含 callables/环境相关对象),并写入 meta sheet.

系统 MUST 满足:
- meta 中 MUST 写入: `derived.<target_id>.fingerprint`
- 当触发护栏失败/截断/冲突等情况时:
  - 系统 MUST 写入结构化 audit 行
  - audit 行 MUST 仅包含: 目标标识/配置指纹/计数统计/稳定的 message hash 等脱敏信息
  - audit 行 MUST NOT 泄露明细行内容与聚合 key 的具体值

治理与兼容约束（新增）：

- `fingerprint` 的用途 MUST 明确为“稳定标识符/对拍与归因”，不得被用于签名、认证、加密等安全目的
- 实现 MUST 使用 `sha256` 生成 fingerprint（hex digest），以避免 `sha1`/`S324` 治理摩擦并提升环境可接受性（例如 `FIPS`）
- 若未来需要变更 fingerprint 算法或输出格式（含 payload 归一化规则），变更 MUST 显式声明其兼容性影响，并且 MUST 选择以下策略之一：
  - `BREAKING`：明确告知 fingerprint 将变化并更新对拍/下游聚合口径
  - 版本化/双写：保留旧 fingerprint 并新增 v2 字段供下游渐进迁移

#### Scenario: 写入派生聚合指纹到 meta
- **WHEN** 运行包含 derived target
- **THEN** 系统 MUST 在 meta 中写入 `derived.<target_id>.fingerprint`

## Notes
- 当前实现侧重 “详情流增量聚合 + finalize 输出 + 资源护栏”. 其它数据来源选择/后置聚合/近似算法属于后续扩展点,本规范先将意图固定以便演进对齐.
