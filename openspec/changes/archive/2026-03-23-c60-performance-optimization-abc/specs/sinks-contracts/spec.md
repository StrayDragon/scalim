# sinks-contracts Specification

## ADDED Requirements

### Requirement: Sinks MAY implement aligned-write fastpath without breaking existing contracts
系统 MUST 在保持现有 `ISink`/`IRowSink`/`IColumnSink` 契约可用的前提下，允许 sinks 通过“可选方法”提供 aligned-write fastpath（见 `sink-fastpath` capability）。

内建 sinks MUST 覆盖该 fastpath（当实现类型适用时），并通过测试保证：
- fastpath 与现有接口写出结果一致
- fastpath 不改变 close/flush 等资源语义

#### Scenario: built-in sinks produce identical output via fastpath
- **WHEN** 内建 sink 同时支持现有接口与 aligned-write fastpath
- **THEN** 在相同输入下两条路径写出的结果 MUST 一致

