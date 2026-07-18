# tasks: c20-sink-discard-explicit-contract

## 0. Specs

- [x] 0.1 delta：`output-sink-contracts` 增加 `discard()` 正式合约（+ 场景）
- [x] 0.2 delta：`execution-structure` 失败收尾 MUST discard（+ 场景）
- [x] 0.3 delta：`execution-output-composition` wrapper MUST 转发 discard（+ 场景）
- [x] 0.4 `llman sdd validate c20-sink-discard-explicit-contract --strict --no-interactive`

## 1. 接口

- [x] 1.1 `ISink`/`IRowSink`/`IColumnSink`（及 Base*）声明并实现 `discard`
- [x] 1.2 内建 file sinks（CSV/Excel/streaming/workbook）覆盖真实 discard
- [x] 1.3 内存类（InMemoryRows/Csv/Column 等）no-op 或清空缓冲（可调用、幂等）
- [x] 1.4 tee/counting/router/composition wrappers 转发 discard

## 2. 执行路径

- [x] 2.1 `run_ir` / pipeline / 装配失败路径仅 discard（回归测试保持绿）
- [x] 2.2 `discard_sink`/`exit_sink` 以正式方法为主；文档化过渡 getattr（若保留）

## 3. Docs / 门禁

- [x] 3.1 可选 upgrade note（若视为用户可见 breaking：自定义 sink 须补 `discard`）
- [x] 3.2 相关单测 + `just qa`
- [x] 3.3 `llman sdd validate c20-... --strict --no-interactive`
