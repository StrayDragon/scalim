## 1. CLI 入口与参数

- [x] 1.1 在 `src/scalim/cli/yaml_dsl.py` 扩展 `yaml-dsl validate` 支持 `--type {auto,demand,workflow}`(默认 `auto`),并在 `workflow` 模式下执行本变更的校验逻辑
- [x] 1.2 增加 `--path-alias <alias>=<path>`(可重复)并解析为 `Dict[str, str]`,用于 `resolve_workflow_demand_path(..., path_aliases=...)`
- [x] 1.3 定义并实现 workflow validate 的 JSON 输出协议(多文件聚合),并保证 exit code: `0`(ok) / `1`(fail)

## 2. 校验实现(静态/编译期)

- [x] 2.1 workflow YAML: 读取文本并构建 `locations = build_yaml_location_index(...)`,复用 `load_workflow_config(...)` 做语义校验,并将异常/错误转为 `Issue`(再 `attach_locations`)
- [x] 2.2 demand YAML: 抽取/复用 `yaml-dsl validate` 的核心逻辑为内部 helper(读取/parse/imports/`ConfigValidator.validate_report`/`attach_locations`),供 workflow validate 递归调用
- [x] 2.3 对每个 `runs[*].demand`:
  - [x] 2.3.1 使用 `resolve_workflow_demand_path` 按 workflow 口径解析实际路径,并在文件缺失时给出可定位错误
  - [x] 2.3.2 对 demand YAML 执行语义校验(允许 imports/$import),错误中需保留可诊断的引用链路
- [x] 2.4 workflow ↔ demand 交叉一致性: 提取 demand 的 `outputs[*].name` 集合,校验每个 `writes[*].*.output` 必须存在;缺失时产生指向 `...output` 的 `Issue`

## 3. 测试

- [x] 3.1 新增 CLI 测试: `writes[*].output` 引用不存在的 output id 时,`yaml-dsl validate --type workflow` 必须失败(对应 spec scenario)
- [x] 3.2 新增 CLI 测试: workflow 引用的 demand YAML 若语义校验失败(unknown fields/imports 错误等),workflow validate 必须失败并输出 demand 侧可定位错误
- [x] 3.3 新增 CLI 测试: `--json` 输出为聚合结构,包含 workflow + demands 的逐文件结果,且 `ok` 与 exit code 一致

## 4. 文档/生成物/门禁

- [x] 4.1 若需要更新 CLI/skills 文档,仅修改 SSOT 并运行 `just gen`(或 `just gen-docs`/`just gen-agent-skill`),不手改 `.gen.*` 与 injected blocks
- [x] 4.2 验收: `pytest`、`just qa`、`just openspec-check`
