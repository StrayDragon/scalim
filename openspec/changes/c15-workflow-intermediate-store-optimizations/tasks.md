## 1. Typed artifact: `InMemoryRows`

- [ ] 1.1 新增 `InMemoryRows` 数据契约（`header: list[str]` + `rows: list[list[FieldValue]]`），并提供 `InMemoryRowsSink`（按 field_id 顺序捕获 typed 值；行长度不匹配时 fail-fast）
- [ ] 1.2 提供显式转换 `InMemoryRows -> InMemoryCsv`（稳定可审计；保序；`None -> ""`，其它 `str(value)`；不得自动生成另一份 artifact）
- [ ] 1.3 单测：`InMemoryRows` 结构校验（header/row 长度、值域为 `FieldValue`）与转换语义（保序 + 规范化）

## 2. `run_ir`: main_rows 注入 + typed rows 捕获

- [ ] 2.1 扩展 `ExecutionRequest`：增加 `main_rows: Optional[Iterable[RowData]]`（默认 `None`）与 `capture_in_memory_rows: bool = False`
- [ ] 2.2 `src/scalim/execution/run_ir.py` 透传 `main_rows` 到 `engine.run(main_rows=..., sink=...)`，确保提供 `main_rows` 时不会触发 main source loader 加载
- [ ] 2.3 在 `capture_in_memory_rows=True` 时，将输出行流 tee 到 `InMemoryRowsSink` 并回填 `ExecutionResult.in_memory_rows`（保持现有 close/cleanup 语义不变）
- [ ] 2.4 单测：`main_rows` 覆盖 main source（loader 不被调用）+ `in_memory_rows` 捕获返回值形状稳定

## 3. workflow runtime: publish / wire / release

- [ ] 3.1 workflow IR/准备阶段推导 `producer_run_id -> remaining_main_rows_consumers` 计数上界（支持多个 consumer 并发读取）
- [ ] 3.2 demand node A 启用 `capture_in_memory_rows` 时，将 `ExecutionResult.in_memory_rows` 发布为 workflow artifact（artifact_id=`in_memory_rows`），并保证可见性边界仍受 `depends_on` 约束
- [ ] 3.3 demand node B 声明 `main_rows_from` 时：从 artifacts 获取上游 `in_memory_rows` 并转换为 `Iterable[RowData]`，注入到 B 的 `ExecutionRequest.main_rows`
- [ ] 3.4 consumer 节点结束（done/failed/cancelled）后递减计数；计数归零时丢弃上游 `in_memory_rows` artifact；workflow 失败/取消时统一丢弃未释放的 typed artifacts
- [ ] 3.5 集成测试：A 产出 typed rows、B 以其作为 main_rows 执行（断言 B 的 main loader 未被调用）；补充多 consumer 并发读取与释放计数的回归用例

## 4. workflow YAML authoring surface + schema drift gate

- [ ] 4.1 增加 workflow YAML 字段 `workflow.runs[*].main_rows_from`（mapping，至少包含 `run: <producer_run_id>`），并在 `workflow_config` 解析阶段提供清晰的错误路径
- [ ] 4.2 编译期校验：consumer MUST 显式 `depends_on` producer；producer run_id 必须存在；否则 fail-fast（路径指向 `workflow.runs[*].main_rows_from` 或 `workflow.runs[*].depends_on`）
- [ ] 4.3 IR 增量：扩展 `src/scalim/spec/ir/workflow.py::WorkflowNodeIr` 增加 `main_rows_from_run_id: Optional[str]`（artifact_id 固定为 `in_memory_rows`）
- [ ] 4.4 **生成物/SSOT 说明**：
  - schema 生成物：`src/scalim/dsl/by_yaml/schema/*.gen.json`（禁止手改）
  - SSOT：workflow schema DSL / models + 解析/编译逻辑
  - 生成入口：`just gen-yaml-dsl-schema`（或直接跑 `just qa`）
  - 验收口径：`just qa` 的 schema drift gate + `openspec validate --all --strict --no-interactive`

## 5. 文档与验收

- [ ] 5.1 若 workflow YAML authoring surface 对用户可见：补充 docs（SSOT 在 `docs/doc/`；任何 `.gen.` 文件禁止手改；用 `just gen-docs` 生成/注入）
- [ ] 5.2 `just openspec-check` 通过（sanitize + `openspec validate --all --strict --no-interactive`）
- [ ] 5.3 `just qa` 通过（包含 ruff/basedpyright/tests/生成物 drift/OpenSpec 校验）
