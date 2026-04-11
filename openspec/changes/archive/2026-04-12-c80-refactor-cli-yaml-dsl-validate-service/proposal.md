## Meta

- Type: `refactor-0`
- Topic: `scalim-cli yaml-dsl validate` 的 CLI 层解耦：把校验逻辑下沉为“纯服务层”，CLI 仅负责 args 与渲染
- Related code:
  - `src/scalim/cli/yaml_dsl.py:909`（`_run_validate`，C901）
  - 现有可复用入口（需求校验已部分存在）：`src/scalim/cli/yaml_dsl.py:816`~`:906`（`_validate_demand_yaml_file` / `_validate_demand_yaml_text`）

## 背景

CLI `validate` 命令当前承担了太多职责：

- 参数解析与路径别名处理；
- schema 路径解析与存在性检查；
- YAML 类型推断（demand/workflow/auto）；
- workflow YAML 的解析 + workflow config 校验；
- workflow 下逐 run 解析 demand 路径并逐个校验 demand YAML；
- 输出（json/text）渲染与错误封装（`ErrorEnvelope`/`ValidationPayload`）；
- 退出码决策。

这些逻辑堆叠在一个 C901 函数中，导致：

- 可维护性差：加一个参数/模式就要修改复杂控制流；
- 可测试性差：很难只测试“校验逻辑”而不同时测试 CLI I/O；
- 复用困难：未来如果需要在 API/服务端复用相同校验能力，会被迫复制逻辑。

该 refactor-0 的目标是：**把校验能力从 CLI 中拆出来成为可复用服务层**，并让 CLI 逻辑薄化。

## 例子（当前痛点）

workflow validate 路径里同时处理：

- workflow YAML 自身的语法/重复 key 校验；
- workflow IR/config 的语义校验；
- 每个 run 的 demand path resolve（含 allowed_yaml_roots、path_aliases）；
- 每个 demand YAML 的 schema 校验与错误定位；
- 合并 workflow_errors 与 demand_results 并渲染输出。

这些步骤天然是一个“pipeline”，但现在以深层嵌套 if/try/except 形式存在，难以增量演进。

## 目标

- 提供纯函数/服务层接口：
  - 输入：yaml_path/schema_path/yaml_type/path_aliases/allowed_yaml_roots 等
  - 输出：结构化 `ValidationPayload`（包含 errors/warnings/locations/附加信息）
- CLI 层只做：
  - args → service 调用
  - payload → renderer（json/text）
  - 返回 exit code
- 保持对外行为一致：
  - 错误码/错误信息关键字段不变或可控；
  - workflow validate 的合并输出结构不变（除非明确治理）。

## 推荐方案

### Phase 0：抽出 service 层模块，不改行为（最小风险）

做法：

- 新增模块：`src/scalim/dsl/yaml_dsl/validation_service.py`
- 将 `_run_validate` 中与渲染无关的逻辑迁移到 service：
  - `validate_demand_file(...) -> ValidationPayload`
  - `validate_workflow_file(...) -> WorkflowValidationResult`（包含 workflow payload + 每个 demand payload）
- CLI 保留 renderer：`_emit_error` / json 输出结构不变。

选择 `dsl/yaml_dsl/` 域而不是 `cli/` 的原因：

- 校验能力属于 YAML DSL 领域能力；CLI 只是一个“前端”，未来 runtime/IDE/server 复用时不应依赖 `cli/` 包。
- 分层清晰：避免服务端/IDE import CLI 的概念污染与潜在循环依赖风险。

收益：

- 单测可直接对 service 层写；
- `_run_validate` 体量明显下降。

### Phase 1：统一 demand/workflow 的错误封装与路径定位

做法：

- 把 `ErrorEnvelope`/`YamlLocationIndex` 的生成集中；
- workflow 与 demand 的 path/loc 规则一致化；
- 对“路径别名/allowed_yaml_roots”这类策略做统一入口，避免漏传。

## 方案对比

### 方案 A：仅拆函数但仍在 `yaml_dsl.py` 内（不推荐作为最终）

优点：

- 改动最小。

缺点：

- 仍然绑在 CLI 文件里，复用与测试收益有限；
- 逻辑边界不清晰。

### 方案 B：抽 service 模块（本提案推荐）

优点：

- 清晰边界：CLI 负责 UI/输出，service 负责业务校验；
- 复用性好（未来 GUI/服务端/API 都能复用）；
- 测试更容易写得细。

缺点：

- 需要更谨慎地保持输出兼容（尤其是错误信息口径）。

## 性价比

- 成本：中（重构面主要在 CLI 校验路径）。
- 收益：高（维护成本显著下降，后续功能演进更稳）。

## 风险与回滚

- 风险：错误输出结构漂移导致脚本/用户预期变化。
- 缓解：
  - Phase 0 以“搬迁但不改逻辑”为主；
  - 增加 CLI 输出快照测试（json/text）覆盖典型错误；
  - 对 workflow validate 结果做 golden fixture。
- 回滚：保留旧函数一段时间，通过 feature flag/内部切换回旧路径（迁移期用，最终移除）。

## 验证建议

- 针对以下场景增加测试：
  - schema 文件缺失；
  - YAML 文件读取失败；
  - workflow YAML 语法错误；
  - workflow config 语义错误；
  - workflow run 中某个 demand path resolve 失败；
  - demand YAML schema 校验失败；
  - json 输出与 text 输出一致性（关键字段）。
