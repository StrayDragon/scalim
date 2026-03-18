## MODIFIED Requirements

### Requirement: workflow MUST precheck Excel output-path collisions across nodes
当 workflow 并发执行多个 nodes 且存在文件输出时,系统 MUST 在“写入发生前”检测潜在的输出路径冲突,避免依赖运行时写锁导致的不确定失败:

- 若多个 nodes 的 demand 输出将写入同一个 xlsx 路径,系统 MUST fail-fast 并指出冲突 nodes 与路径
- 若路径可在结构编译阶段静态提取,冲突 MUST 在结构编译阶段 fail-fast
- 若路径依赖 `init_vars/$ctx` 等动态渲染,冲突 MUST 在 node 物化编译后、实际写入前 fail-fast
- 若某个 xlsx 路径被 workflow 声明为共享输出资源(例如 `resources.workbooks[*].path` 或 `resources.sheetbooks[*].export_xlsx.path`),系统 MUST 禁止 nodes 直接写该路径（必须通过共享资源 + 写出节点/commit 流程）

#### Scenario: duplicate xlsx output paths are rejected deterministically
- **GIVEN** 两个 nodes 的 demand 都声明输出到同一个 xlsx 路径
- **WHEN** workflow 被编译/校验
- **THEN** 系统 MUST fail-fast 并报告冲突路径与节点 id

#### Scenario: dynamic init_vars output path participates in collision checks using resolved path
- **GIVEN** workflow 包含两个 runs: A 与 B
- **AND** run A 的 demand 声明 `outputs[0].container.path={$init_var: output_path}`
- **AND** run B 的 demand 声明 `outputs[0].container.path={$init_var: output_path}`
- **AND** workflow 运行时为 A 注入 `init_vars={"output_path": "./out/a.xlsx"}`
- **AND** workflow 运行时为 B 注入 `init_vars={"output_path": "./out/b.xlsx"}`
- **WHEN** workflow 执行并物化编译每个 node
- **THEN** 系统 MUST NOT 将 `{$init_var: output_path}` 的字面结构字符串化后参与 collision 判断
- **AND** 系统 MUST 以最终解析后的绝对路径（`./out/a.xlsx` 与 `./out/b.xlsx`）作为判定基准

#### Scenario: dynamic ctx-derived output path fails-fast before write
- **GIVEN** run B 的 demand 输出路径由 `workflow.runs[B].init_vars` 使用 `$ctx` 引用 run A 的运行摘要并拼装得到
- **WHEN** run B 的 node 被物化编译且其 `init_vars` 已完成 `$ctx` 渲染
- **THEN** 系统 MUST 在实际写入发生前对渲染后的最终路径执行 reserved/collision 检查
- **AND** 若触发冲突,系统 MUST fail-fast 并报告最终 path 与冲突 nodes

#### Scenario: reserved xlsx paths are checked using resolved dynamic path
- **GIVEN** workflow 声明 `workflow.resources.sheetbooks.report.export_xlsx.path=./out/report.xlsx`
- **AND** 某个 run 的 demand 声明 `outputs[0].container.path={$init_var: output_path}`
- **AND** 该 run 的 `init_vars={"output_path": "./out/report.xlsx"}`
- **WHEN** workflow 物化编译该 run 且准备执行写入
- **THEN** 系统 MUST fail-fast 并报告该路径被 workflow shared resources 保留（必须使用 resources + write nodes）

