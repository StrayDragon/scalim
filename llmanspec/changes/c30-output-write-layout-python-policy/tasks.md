# Tasks: OutputWriteLayout

## 1. Specs landing

- [x] 1.1 新增 `llmanspec/specs/runtime-output-write-layout/spec.toon`（闭集 Enum、优先级、互斥 fail-fast、工厂映射、手写 sink 绕过）
- [x] 1.2 修订 `yaml-dsl-runtime-policy-boundary`：layout 仅 Python；composition 与非 `row_stream` fail-fast；保留/交叉引用 r176
- [x] 1.3 修订 `streaming-output`：文件 sink 工厂按 effective layout 选择（指针级 r1108）
- [x] 1.4 更新 docs capability-matrix / yaml-dsl review-checklist 对应行；excel-column-residency 指向 `OutputWriteLayout`

## 2. Enum + options 面

- [x] 2.1 [blocked-by: 1.1] 实现 `OutputWriteLayout`（`StrEnum`）于 `src/scalim/execution/`（或紧邻 residency 模块）并导出
- [x] 2.2 [blocked-by: 2.1] `DemandRunRuntimeOptions` / `ExecutionRequest` 增加 `output_write_layout`（Optional=None 表示推导；Enum-only）
- [x] 2.3 [blocked-by: 2.2] 编译路径把 options 传入 `ExecutionRequest`；pytest：拒 str、接受 Enum

## 3. 归一与工厂

- [x] 3.1 [blocked-by: 2.2] 实现 `resolve_output_write_layout(...)`（显式 > 推导 > 默认；单测覆盖推导表，含 csv+WINDOW→column_hold）
- [x] 3.2 [blocked-by: 3.1] `_create_file_sink` / run_ir 按 effective layout 选 sink；统一 fail-fast 文案
- [x] 3.3 [blocked-by: 3.2] 回归：未设 layout 时 csv/excel × streaming × residency 组合 sink 类型不变
- [x] 3.4 [blocked-by: 3.2] fail-fast 测：composition+显式 column_*；显式 csv+column_window；YAML 非法字段（若 parser 面可达）

## 4. Docs / agent

- [x] 4.1 [blocked-by: 3.2] 更新 `excel-column-residency.md`、streaming-column-excel-guidance、notplan D3 状态指针
- [x] 4.2 [blocked-by: 4.1] New knob gate / AGENTS 指针一句（layout = Python）

## 5. 性能与收尾

- [x] 5.0 [blocked-by: 3.3] 默认路径 ≥5 跑基线 vs after：median 墙钟/peak RSS 回归 ≤ ~5%；证据 `.tmp/evidence/c30-output-write-layout/`
- [x] 5.1 [blocked-by: 3.3, 3.4, 4.1, 5.0] `llman sdd validate c30-output-write-layout-python-policy --strict` + 相关 pytest 绿
