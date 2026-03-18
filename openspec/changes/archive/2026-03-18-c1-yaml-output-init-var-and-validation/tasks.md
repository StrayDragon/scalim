## 1. `value_cast` 的 `None` 语义修复

- [x] 1.1 修改 `src/scalim/dsl/by_yaml/runtime/_internal/conversion_lookup.py` 的 `cast_str/cast_int`: `value is None` 时直接返回 `None`
- [x] 1.2 补充回归测试: 覆盖 `value_cast: str/int` + `None` 的透传行为,并包含一个 `compute` 的 `if x else ...` 场景防止 `"None"` 回归

## 2. `outputs.*.container.path` 支持 `{$init_var: ...}` 并编译期解析

- [x] 2.1 更新 schema SSOT: `src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py` 中 `OutputContainerConfig.path` 的 schema 改为 `oneOf(string | {$init_var: string})`
- [x] 2.1.1 更新 `OutputContainerConfig.path` 的 `markdownDescription`/示例: 明确 `{$init_var: <name>}` 为**对象节点**(非字符串插值),且仅编译期解析一次
- [x] 2.2 重新生成生成物 `src/scalim/dsl/by_yaml/schema/demand.gen.json`(禁止手改 `.gen.`):
  - SSOT: `src/scalim/dsl/by_yaml/schema_dsl/`
  - 生成入口: `scripts/gen-yaml-dsl-schema.py` / `just gen-yaml-dsl-schema`
  - 验收口径: `tests/test_yaml_schema_generation.py` drift check 通过
- [x] 2.3 修改 `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py::_parse_output_container`: 允许 `path` 为 `{$init_var: ...}` mapping,禁止将 dict `str()` 化,并在无 jsonschema 环境仍能对非法形态 fail-fast
- [x] 2.4 在线路上引入 init_vars 解析(编译期):
  - 让 `compile_output_composition_from_yaml(...)` 接收 `init_vars`
  - 在 `_output_spec_from_container/_compile_extra_sheet` 等处将 `{$init_var: ...}` 解析为最终非空字符串路径:
    - 缺失 init_var 时 fail-fast,报出 `outputs.<i>.container.path` 等明确路径
    - 解析结果 MUST 为 `str` 或 `os.PathLike`,并且 `strip()` 后非空(否则 fail-fast)
- [x] 2.5 补充测试:
  - init_vars 存在时 `{$init_var: output_path}` 可写出到预期路径
  - init_vars 缺失时 fail-fast 且错误包含 `outputs.0.container.path`

## 3. 修复 `run_ir` 吞 close 异常导致的静默失败

- [x] 3.1 修改 `src/scalim/execution/run_ir.py` 的 finally 清理语义:
  - `engine.run()` 成功: `sink.close()` 异常必须传播
  - `engine.run()` 失败: close best-effort,不得覆盖原异常(可记录日志)
- [x] 3.2 增加单测: 构造一个会在 close 抛异常的 sink,验证“run 成功但 close 失败 => run_ir 失败”的行为
- [x] 3.3 增加单测: 构造 `engine.run` 抛异常 + close 也抛异常,验证最终抛出的是原执行异常

## 4. CLI `yaml-dsl validate` 默认严格 + best-effort JSONSchema

- [x] 4.1 修改 `src/scalim/cli/yaml_dsl.py`: 移除 `yaml-dsl validate` 与 `yaml-dsl schema validate` 的 `--strict` 参数,默认严格未知字段
- [x] 4.2 修改 CLI validate 的实现: 默认开启 `enable_jsonschema_validation=True`(jsonschema 缺失/异常时以 warning 呈现但不影响内部语义校验)
- [x] 4.3 调整 `validate_yaml_text(...)` 的成功判定: warnings 不应导致失败;严格模式通过 unknown-fields 产出 errors 体现即可
- [x] 4.4 更新回归测试(`tests/test_yaml_dsl_cli_output.py` 等): 对齐新的参数/输出/退出码语义,并覆盖“无 jsonschema 时有 warning 但 validate 仍成功”的场景

## 5. 文档/技能提示: 指令节点范围约束

- [x] 5.1 更新 `docs/doc/yaml-dsl/capability-matrix.md`: 明确 `{$init_var: <name>}` 的允许位置范围(含 `outputs.*.container.path`),并强调“对象节点/编译期一次性解析/不做子串插值”
- [x] 5.2 更新 `docs/doc/yaml-dsl/user-guide.md` 与 `docs/doc/yaml-dsl/syntax.md`:
  - 增加 `$init_var/$keys/$rows` 的范围约束表(允许/禁止位置)
  - 更新 CLI 示例: 移除 `--strict`(默认 strict)
  - 避免改动任何 `<!-- BEGIN AUTOGEN:... -->` 注入区块内部
- [x] 5.3 更新 `artifacts/skills/scalim-yaml-dsl/references/task-authoring.md` 与 `artifacts/skills/scalim-yaml-dsl/references/task-validate-debug.md`:
  - 补充 `outputs.*.container.path: {$init_var: ...}` 示例与风险提示(例如临时目录生命周期)
  - 更新命令示例去掉 `--strict`,并明确 validate/schema validate 的默认行为
- [x] 5.4 如有 docs 注入/生成漂移: 运行 `just gen-docs` 并确保仅产生预期变更

## 6. 回归与验收

- [x] 6.1 运行目标测试集(优先最小集,再跑全量): `pytest -q` / `just qa`
- [x] 6.2 运行 OpenSpec 校验(分享/发布前): `just openspec-check`
