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

## Notes
- 当前实现侧重 “详情流增量聚合 + finalize 输出 + 资源护栏”. 其它数据来源选择/后置聚合/近似算法属于后续扩展点,本规范先将意图固定以便演进对齐.
