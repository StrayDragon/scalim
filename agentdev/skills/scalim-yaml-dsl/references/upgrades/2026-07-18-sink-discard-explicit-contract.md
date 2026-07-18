# 2026-07-18 — `ISink.discard` 显式失败清理合约

## Breaking（窄）

自定义 `ISink` / `IRowSink` / `IColumnSink` 实现 **MUST** 提供 `discard()`：

- 失败路径清理；`MUST NOT` 把半成品 promote 到最终输出路径
- 无文件副作用时可为可调用的 no-op（建议幂等）
- 成功提交仍只用 `close()`

若只实现了 `write_*` + `close`，在 Python ABC 下将无法实例化。

## 迁移

```python
class MySink(IRowSink):
    def write_row(self, row):
        ...

    def close(self):
        ...  # 成功落盘

    def discard(self):
        # 失败:关闭句柄/删 temp；不要 atomic replace 到最终路径
        ...
```

继承 `BaseSink` / `BaseRowSink` / `BaseColumnSink` 时已有默认 no-op `discard`；有状态/文件副作用的子类应覆盖。

## 相关

- 承接：`tabular-bus-object-sink-accept-precheck`（duck-typed discard MVP）
- 规格：`output-sink-contracts` r922/r923/r924；`execution-structure` r925
