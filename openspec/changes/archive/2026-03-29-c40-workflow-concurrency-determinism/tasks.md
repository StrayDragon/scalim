## 1. Observer 并发语义（默认安全）

- [x] 1.1 选择并落地默认策略：capture+replay（优先）或 per-observer 锁序列化；并保持 `no-external-callback-under-lock` 不被破坏。
- [x] 1.2 在并发 workflow 下增加回归：注册一个非线程安全 observer（含可变状态），确保回调不并发执行且事件序列可解释/可复现。
- [x] 1.3 明确并实现事件排序策略（编排级事件至少稳定），并增加“并发重复运行顺序一致”的回归测试。

## 2. Viz 输出并发写入保护

- [x] 2.1 为 `VizEventEmitter` 引入单写者语义（锁或仅允许在 replay/drain 阶段调用），确保 JSONL 行不交错。
- [x] 2.2 增加回归：并发产生多条 viz 事件后，`viz_events.jsonl` 可逐行 JSON 解析。

## 3. 共享资源写入确定化（声明顺序 SSOT）

- [x] 3.1 为 write intents/segments 引入稳定 `decl_order`，commit 阶段按 `decl_order` 排序写出（禁止依赖线程完成时序）。
- [x] 3.2 修复 workbook/sheetbook 的 sheet 顺序漂移：按声明顺序或显式规则稳定排序。
- [x] 3.3 增加确定性回归：并发执行多次，csv/workbook/sheetbook 输出一致（尤其是 append 段顺序与 sheet 顺序）。

## 4. 写锁与锁文件治理

- [x] 4.1 统一并强化最终输出的默认写锁策略（避免跨进程静默覆盖），并在冲突时给出可操作诊断（包含 owner 信息）。
- [x] 4.2 为锁文件残留提供治理策略（例如 TTL/force-unlock 或更友好提示），并增加对应回归测试。

## 5. run_id 唯一性

- [x] 5.1 将 `run_id` 生成改为高熵策略（例如 uuid4），并修复相关测试/文档假设。

## 6. 文档与验收

- [x] 6.1 更新 workflow 并发与可观测性文档（SSOT 在 `docs/doc/**`；生成/注入区块按 `just gen-docs` 刷新）。
- [x] 6.2 运行 `just qa` 与 `just openspec-check`，确保门禁与规范校验通过。
