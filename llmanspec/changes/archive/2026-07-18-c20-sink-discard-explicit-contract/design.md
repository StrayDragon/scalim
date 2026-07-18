# Design: c20-sink-discard-explicit-contract

## 目标语义

| 方法 | 何时 | 语义 |
|------|------|------|
| `close()` | 成功路径 | 提交/落盘/finalize；file sink 原子 replace |
| `discard()` | 失败路径 | 放弃半成品；`MUST NOT` promote 最终用户路径；可 best-effort 关句柄/清 temp |

二者互斥：同一 sink 实例在一次生命周期内，失败收尾走 `discard` 后不得再成功 `close` promote。

## 接口落地（Python 3.6）

推荐：

```python
class ISink(ABC):
    @abstractmethod
    def write_batch(...): ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def discard(self) -> None:
        """失败路径清理；无副作用时可为 no-op，但 MUST 可调用。"""
```

- `BaseSink` / `BaseRowSink` 提供默认 `discard` no-op（内存无文件副作用），文件类覆盖。
- Wrapper（tee/counting/router/`_CountingOutputRowSink`）MUST 转发给内部 sink。
- `ExcelWorkbookSink` 与 sheet row sink：workbook 级 discard 放弃整本；sheet 级 discard 与 workbook 生命周期对齐（design 实施时写清：优先 workbook.discard）。

## Helper

- `discard_sink(sink)`：调用 `sink.discard()`（合约落地后为主路径）。
- `exit_sink`：异常 → `discard`；成功 → `close`。
- 过渡：若仍存在非 ABC 第三方对象，MAY 短期保留 getattr；tasks 里标 deprecate。

## 与 r922 关系

- `r922` 继续约束「不得半残最终文件」。
- 本 change 新增：`discard()` 为满足 r922 的 **API SSOT**（执行层不得用 `close()` 代替失败清理）。

## 测试 / 门禁

- 抽象：未实现 `discard` 的假 sink 在子类化时失败（或运行时契约测试）。
- 行为：沿用/扩展 c15 测试——`run_ir` mid-fail、ColumnExcel CM 异常、router discard 转发、无最终文件。
- `just qa` 全绿。

## 非目标细节

- 不引入 YAML。
- 不改变 accept set / `SinkTypePrecheck`。
