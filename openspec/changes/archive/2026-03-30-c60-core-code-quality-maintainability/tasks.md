## 1. 生成物清单 SSOT（drift checks 收敛）

- [x] 1.1 新增 generated-artifacts manifest（机器可读），登记 schema/docs/editor 等生成物与生成入口（脚本/`just` 目标）。
- [x] 1.2 将 `justfile` 中硬编码的 drift checks 重构为读取 manifest 的单一脚本入口（失败信息仍需可定位到生成入口）。
- [x] 1.3 增加回归：新增生成物但未登记 manifest 时 fail-fast。

## 2. 异常类型收敛（同名重复定义消除）

- [x] 2.1 收敛 `ScalimWorkflowConfigError` 等重复定义为单一 canonical 类型，并更新 DSL/workflow 入口只做包装补充上下文（path/loc/source）。
- [x] 2.2 增加回归：同一类配置错误在 CLI/compile/workflow validate 下的类型与对外消息一致。

## 3. 错误对外消息策略统一（默认 redacted）

- [x] 3.1 引入单点“异常→对外消息”格式化工具（默认 redacted，显式 debug 才 full），并在 CLI JSON/viz/workflow report 等出口统一使用。
- [x] 3.2 增加回归：同一异常在不同出口呈现保持一致结构且不泄露敏感值。

## 4. 日志一致化（禁止 runtime print）

- [x] 4.1 盘点并移除 runtime 路径中的 `print(...)`，统一改为结构化 logger（优先 `loggingx`）。
- [x] 4.2 增加 gate：`src/scalim/**` 中出现 `print(` 则 fail-fast（允许测试/工具脚本按白名单例外）。

## 5. 热点模块拆分（小步行为等价重构）

- [x] 5.1 选择一个热点模块作为试点拆分（例如 workflow execute / YAML workflow_config / output_composition），按“领域+阶段”拆成职责单一模块。
- [x] 5.2 增加行为等价护栏：拆分前后输出/事件/错误语义一致（复用现有 examples/spec checks，必要时补充单测）。
- [x] 5.3 增加模块体量 guardrail（先 warn-report，再提升为 fail-fast），防止回归为巨型文件。

## 6. 其它可维护性 guardrails

- [x] 6.1 为事件 dispatch map 增加完整性校验（新增核心事件需显式加入/忽略）。
- [x] 6.2 为 `src/scalim/_internal/utils` 添加极短治理说明（允许进入的内容类型/依赖方向/迁移策略）。

## 7. 验收

- [x] 7.1 运行 `just qa` 与 `just openspec-check`，确保门禁通过且无生成物漂移。
