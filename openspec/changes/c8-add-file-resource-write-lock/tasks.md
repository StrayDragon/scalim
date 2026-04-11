## 1. YAML DSL SSOT + Schema 生成

- [ ] 1.1 在 `src/scalim/dsl/yaml_dsl/schema_dsl/models/resources.py` 为 `FileConfig` 新增 `write_lock: bool = False`(并补齐 schema_meta 描述)
- [ ] 1.2 运行 `just gen-yaml-dsl-schema` 生成 `src/scalim/dsl/yaml_dsl/schema/{demand,workflow}.gen.json`（禁止手工编辑任何 `*.gen.*`）
- [ ] 1.3 运行 `just schema-drift-check` 确认 schema 生成物无漂移

## 2. YAML 解析(需求/工作流)

- [ ] 2.1 更新 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/loader.py` 的 `_parse_file_config` 支持 `write_lock` 并保持 unknown keys fail-fast
- [ ] 2.2 更新 `src/scalim/dsl/yaml_dsl/workflow_config/_parse.py` 的 `_parse_file_config` 支持 `write_lock` 并保持类型校验

## 3. Overrides 数据模型(typed)与 overlay

- [ ] 3.1 在 `src/scalim/dsl/yaml_dsl/runtime/contracts.py` 为 `FileResourceOverride` 增加 `write_lock: Optional[bool]`
- [ ] 3.2 更新 `src/scalim/dsl/yaml_dsl/runtime/compiler.py` 的 `_apply_file_override` 以 overlay `write_lock` 并保持类型校验
- [ ] 3.3 更新 `src/scalim/dsl/yaml_dsl/workflow_compile.py` 的 `_file_override_to_patch` / `_apply_file_patch` 支持 `write_lock`

## 4. IR 传递(compile → execute)

- [ ] 4.1 更新 `src/scalim/dsl/yaml_dsl/workflow_compile.py` 的 `_file_export_path_and_options` 将 `write_lock` 写入 `WorkflowResourceIr.options`
- [ ] 4.2 若 standalone demand 编译路径同样需要导出该选项,同步更新对应编译器(与 workflow compile 保持一致)

## 5. Standalone 输出组合 + CSV sink 写锁

- [ ] 5.1 更新 `src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py` 的 `_output_spec_for_file_resource` 将 `resources.files.*.write_lock` 写入 `OutputSpec.write_lock`
- [ ] 5.2 扩展 `src/scalim/execution/output_composition.py` 的 `_create_csv_sink` 与 `src/scalim/execution/run_ir.py` 的 `_create_file_sink` 在创建 CSV sink 时传入 `write_lock`
- [ ] 5.3 为 `src/scalim/sinks/_internal/sink_csv.py` 的 `CSVSink` 与 `ColumnCSVSink` 增加 `write_lock` 参数(默认 false),并在 `close()` 的原子 replace 边界获取/释放 lockfile

## 6. Workflow publish 执行写锁

- [ ] 6.1 在 `src/scalim/workflow/execute.py` 的 `_build_workflow_resource_defs` 解析 csv resource options 并构建 `csv_write_lock_by_id`
- [ ] 6.2 扩展 `src/scalim/workflow/resources_base.py` 的 resource manager 初始化参数/字段以接收 `csv_write_lock`
- [ ] 6.3 在 `_WorkflowResourceManagerBase._publish_staged_outputs` 中对 `resource_type=\"csv\"` 且 `write_lock=true` 的 staged outputs 在 publish 边界获取/释放写锁（锁覆盖 replace 与 copy-atomic 两条路径）

## 7. 测试

- [ ] 7.1 在 `tests/workflow/test_workflow_resources_coverage.py` 增加 CSV publish 写锁用例：`write_lock=True` 时并发 publish 必须 fail-fast 抛出 `ScalimWorkflowWriteError`
- [ ] 7.2 增加对照用例：`write_lock=False` 时 publish 不得因锁冲突失败（允许覆盖）
- [ ] 7.3 增加 standalone CSV sink 的并发/冲突用例(或复用现有测试结构): `write_lock=True` 时 fail-fast,`write_lock=False` 时不因锁冲突失败

## 8. 规范同步与验收门禁

- [ ] 8.1 运行 `just openspec-check` 校验 OpenSpec 工件
- [ ] 8.2 跑 `just qa` 作为最终验收：tests + lint/format + drift checks 全绿
