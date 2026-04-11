# flow-visualization (delta) Specification

## ADDED Requirements

### Requirement: viz snapshot JSON output MUST be atomic and remain parseable under concurrency

当系统将 `VizGraphSnapshot` 落盘为 `viz_snapshot.json` 时，系统 MUST 保证写入原子性，避免读者读到半写文件或损坏 JSON：

- 系统 MUST 以“写入临时文件 + 原子替换（temp+replace）”的方式生成 `viz_snapshot.json`
- 在写入完成之前，读者读取目标路径时 MUST 看到旧版本（若存在）而不是半写内容
- 即使存在并发/重入写同一路径，最终落盘的 `viz_snapshot.json` MUST 始终可被 JSON 解析（允许最后写入者覆盖）

#### Scenario: concurrent snapshot writers do not corrupt JSON
- **GIVEN** 两个并发执行单元（线程或进程）写入同一个 `viz_snapshot.json` 目标路径
- **WHEN** 两者几乎同时触发 snapshot 写入
- **THEN** 文件内容 MUST 始终为可解析的 JSON
- **AND** 读者在任意时刻读取该路径 MUST 看到“旧版本或新版本”，不得读到半写文件

