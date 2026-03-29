## ADDED Requirements

### Requirement: Viz JSONL output MUST remain valid under concurrency

当并发执行产生 VizEventStream 且事件发射可能来自多个线程时,系统 MUST 保证输出的 JSONL 文件在并发下仍然可解析:
- 每一行 MUST 为完整 JSON 对象
- 行与行之间 MUST 不交错、不出现半行

#### Scenario: concurrent emission does not corrupt JSONL
- **WHEN** workflow 并发执行并触发多条 viz 事件
- **THEN** 输出的 `viz_events.jsonl` MUST 可被逐行 JSON 解析

### Requirement: run_id MUST be collision-resistant

系统 MUST 使用高熵的 run_id 生成策略,避免并发启动（同毫秒）导致的 run_id 碰撞与输出目录争用.

#### Scenario: parallel runs get distinct run_id
- **WHEN** 系统在极短时间内并发启动多个 run
- **THEN** 每个 run 的 `run_id` MUST 不相同

