## Why

workflow 的资源输出采用 staging → publish 两阶段；当多个 workflow 进程并发写同一 `final_path` 时会出现“最后写入者胜”的静默覆盖。

目前 `books` 已支持 `write_lock`（并计划/正在修复 publish 阶段强制执行），但 `files.kind=csv_file` 没有 `write_lock` 入口，导致 CSV 这类“最终落盘到固定路径”的业务场景无法 fail-fast 防止覆盖。

## What Changes

- 在 YAML DSL `resources.files.<file_id>`（`kind=csv_file`）新增可选字段：
  - `write_lock: bool`（默认 `false`）
- **standalone demand** 与 **workflow** 两条运行路径均在最终文件写入边界强制执行写锁：
  - standalone：在 `CSVSink/ColumnCSVSink.close()` 的原子 replace 边界对 `output_path` 获取跨进程写锁
  - workflow：在 publish(staged → final) 边界对 `final_path` 获取跨进程写锁
  - 锁文件为 `<final_path>.scalim.lock`，冲突时 fail-fast 并提供可诊断错误（包含 `lock_path` 与 lock owner 信息）。
- `RunOverrides.resources.files.*` 增加对应字段（IO-only overlay），允许在不改 YAML 的情况下为某个 file resource 打开/关闭写锁。
- 增加覆盖/并发 publish 的测试用例，确保：
  - `write_lock=true` → 并发 writer fail-fast
  - `write_lock=false` → 不因锁冲突失败（允许覆盖，保持历史行为）

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `yaml-dsl-file-resources`: 为 `csv_file` 定义 `write_lock` 配置与 publish 互斥语义（默认 false，启用时 fail-fast）。
- `yaml-dsl-output-overrides`: 允许 IO-only overlay 覆盖 `files.*.write_lock`（与 `books.*.write_lock` 同类）。

## Impact

- YAML DSL SSOT + 生成物：
  - SSOT：`src/scalim/dsl/yaml_dsl/schema_dsl/models/resources.py`（新增 `FileConfig.write_lock`）
  - 生成物：`src/scalim/dsl/yaml_dsl/schema/{demand,workflow}.gen.json`（禁止手改；通过生成入口更新）
- 编译与 IR：
  - `src/scalim/dsl/yaml_dsl/workflow_compile.py` / `src/scalim/dsl/yaml_dsl/runtime/compiler.py`：解析/overlay 并把 `write_lock` 传入 IR options
- 运行时：
  - standalone：`src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py` → `src/scalim/execution/{output_composition.py,run_ir.py}` → `src/scalim/sinks/_internal/sink_csv.py`（在 sink close 边界执行锁）
  - workflow：`src/scalim/workflow/execute.py` / `src/scalim/workflow/resources_base.py`（在 publish 边界强制执行 CSV 写锁）
- QA/验收：
  - `just openspec-check`（OpenSpec 工件校验）
  - `just qa`（lint/tests + drift checks）
