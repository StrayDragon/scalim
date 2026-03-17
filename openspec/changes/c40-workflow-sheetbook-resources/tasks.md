## 1. Workflow schema & IR surface

- [ ] 1.1 扩展 workflow schema/IR：新增 `resources.sheetbooks` 与对应的 IR 表示（Python 3.6 兼容）
- [ ] 1.2 定义 sheetbook 的 authoring surface：
  - `resources.sheetbooks[*].budget.max_sheets/max_total_cells`
  - `resources.sheetbooks[*].export_xlsx.path/write_lock`（导出在资源 commit 阶段执行）
  - `runs[*].write_to.sheetbook_sheet/sheetbook_append`（编译后解糖为显式 write nodes）
- [ ] 1.3 静态校验：sheetbook id 唯一、sheet 名合法、deps 可见性约束可被校验

## 2. Sheetbook resource manager

- [ ] 2.1 定义 `SheetBook` 数据表示（推荐：sheet -> 列式内存表示），并支持 read/write/append
- [ ] 2.2 实现资源生命周期：create/hold/release/discard（与 DAG refcount/生命周期方向对齐）
- [ ] 2.3 实现预算护栏：max_sheets/max_total_cells（超限 fail-fast，错误摘要可读）

## 3. Deterministic writes

- [ ] 3.1 实现对同一 sheetbook 的互斥/串行写入（不依赖并发完成顺序）
- [ ] 3.2 实现冲突检测：sheet 名重复、重复写入、字段对齐冲突 fail-fast（错误摘要可读）

## 4. Export to xlsx (atomic)

- [ ] 4.1 实现 sheetbook -> xlsx 的导出（资源 commit 阶段；临时文件 + 原子替换）
- [ ] 4.2 适配 write_lock：导出阶段使用 `.scalim.lock` 防并发写
- [ ] 4.3 失败语义：失败即 discard，不产生“已提交但不完整”的最终 xlsx（v0 不支持 partial commit）

## 5. Consume sheetbook as demand input

- [ ] 5.1 提供内置 loader `scalim.dsl.by_yaml.runtime.workflow_loaders:sheetbook_sheet_rows` 读取 `<node_id, sheet_name>` 对应的 rows
- [ ] 5.2 实现 deps 可见性校验：禁止读取非依赖闭包的 sheetbook
- [ ] 5.3 错误诊断：不存在的 sheet/越界引用必须 fail-fast 并给出摘要

## 6. Excel output-path collision precheck

- [ ] 6.1 在 workflow 编译/校验阶段扫描各 nodes 的 demand 输出路径，检测 xlsx 路径冲突并 fail-fast
- [ ] 6.2 当路径已被声明为共享资源时，禁止 nodes 直接写该路径（必须通过写出/导出节点）

## 7. Observability integration

- [ ] 7.1 发出资源生命周期事件（`workflow_resource_create/write/commit/discard`）并复用 `workflow_exec_id` / `workflow_node_id`
- [ ] 7.2 事件可 join 回 DAG：并发下不串扰，顺序可解释

## 8. Docs/tests/gates

- [ ] 8.1 更新 docs 与示例（SSOT 为 `docs/doc/**`；如涉及 injected blocks 或 `.gen.*`，通过 `just gen-docs` 生成）
- [ ] 8.2 新增测试：确定性写入、预算护栏、deps 可见性、collision precheck、失败 discard 行为
- [ ] 8.3 运行 `just qa`
- [ ] 8.4 运行 `just openspec-check`
