> Status (2026-03-11): 已实现(IR/Python-only),任务清单全部完成;待 `just qa`/`just gen` 全量验收后归档。

## 0. Scope & Defaults (Re-open Checklist)

- [x] 0.1 明确 failure policy 默认值（主输出优先 vs 全失败），并写入 spec/design
- [x] 0.2 明确 `adaptive` 下的派生聚合一致性边界（允许/禁止/需 seq），并给出 fail-fast 规则
- [x] 0.3 明确命名冲突策略：sheet 名冲突默认 error（不得静默覆盖/隐式改名）

## 1. Workbook Container & Multi-Sheet Sinks (Memory & Robustness First)

- [x] 1.1 引入 workbook 容器型输出模型：单次运行可向同一 workbook 写入多个 sheet
- [x] 1.2 实现多 sheet 的流式写入（write_only/stream），避免“全量 rows 攒内存”
- [x] 1.3 sheet 名冲突 fail-fast；输出顺序稳定可控（便于 compare）
- [x] 1.4 header 与 rows 分离建模，避免 header list 被复用污染/extend
- [x] 1.5 增加针对多 sheet workbook 的单元/集成测试（含冲突/顺序/内存模型）

## 2. Output Composition Layer (Tee/Router)

- [x] 2.1 引入多输出目标的运行时组合器（保持单输出路径兼容）
- [x] 2.2 TeeRowSink / RouterRowSink：同一明细流多路分发到多张 sheet（Detail/FilteredDetail/Audit/Summary）
- [x] 2.3 Filter/Select 等轻量行变换（用于 FilteredDetail/Audit），并保证流式写入
- [x] 2.4 instrumentation：每张 sheet 的行数/耗时/错误计数可观测（为 meta/audit 提供数据）

## 3. Derived Output Aggregation (Summary/RankedSummary)

- [x] 3.1 定义最小增量聚合接口与生命周期（init/accumulate/finalize）
- [x] 3.2 内置 streaming-friendly 聚合（count/sum/min/max/count_true）+ `group_by`
- [x] 3.3 RankedSummary：支持 finalize 后排序/排名（或二阶段兜底），并明确默认策略
- [x] 3.4 资源控制：高基数键的状态上限/近似/必要的落盘或溢出策略（可先仅做 guardrails）
- [x] 3.5 增加聚合相关测试：正确性、并发边界（`seq|adaptive`）、失败策略

## 4. Meta/Audit Standardization (Compare Friendly)

- [x] 4.1 MetaSheet：运行参数、配置 hash、版本信息、各 sheet 行数/耗时（标准化结构）
- [x] 4.2 AuditSheet：常见排除/缺失映射/异常清单的框架化输出（至少提供最小钩子）
- [x] 4.3 增加对拍友好的固定输出顺序与字段规范（避免 compare 误报）

## 5. MultiRootSheets (Workbook as Container of Demands)

- [x] 5.1 workbook 允许每张 sheet 绑定独立 demand（多根数据源）
- [x] 5.2 明确与缓存/复用/并发的交互规则（避免重复执行与不可解释结果）
- [x] 5.3 增加 multi-root 的集成测试（多 sheet + 多 demand）

## 6. Docs, Examples, And Verification

- [x] 6.1 更新用户文档与示例：解释该能力仅 IR/Python 配置，展示 workbook 多 sheet + 派生汇总概念
- [x] 6.2 新增验证用例：命名冲突、失败策略、顺序稳定、meta/audit、资源 guardrails
- [x] 6.3 运行 `openspec validate add-derived-outputs --strict --no-interactive` 并补充必要的实现期校验命令说明
