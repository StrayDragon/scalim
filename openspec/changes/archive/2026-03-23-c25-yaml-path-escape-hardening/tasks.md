## 1. allow-roots helper（SSOT：yaml-dsl-allowed-paths-policy）

- [ ] 1.1 新增统一 helper 模块（例如 `src/scalim/dsl/by_yaml/config_parsing/allowed_paths.py`）：归一化 roots + `resolved_path` 的 `relative_to` 校验 + 统一错误构造（raw/base_dir/resolved/roots）
- [ ] 1.2 定义并固化默认 roots 语义：未显式传入时默认包含入口 YAML 所在目录（demand: `yaml_path.parent`；workflow: `workflow_yaml_path.parent`）
  - 备注：该 helper 与错误格式将作为后续 `yaml-dsl-import-aliases-and-presets` 的 roots/aliases 校验复用点（避免两套口径漂移）

## 2. demand imports：接入 allow-roots 校验

- [ ] 2.1 扩展 `expand_imports_inplace` / `load_and_expand_imports` API：增加 `allowed_yaml_roots`（或等价 policy）参数，并在 `resolve()` 后执行 roots 校验
- [ ] 2.2 更新 call sites（至少 `YamlDemandLoader` 与 `scalim-cli yaml-dsl validate` 路径）传递默认 roots/显式 roots
- [ ] 2.3 单测：`imports: ../../secrets.yaml` 在默认 roots 下 fail-fast；显式扩展 roots 后成功

## 3. workflow runs demand + path aliases：接入 allow-roots 校验

- [ ] 3.1 扩展 `resolve_workflow_demand_path(..., allowed_yaml_roots=...)`（或等价）并在最终 `resolve()` 后做 roots 校验（覆盖相对/绝对/alias 三类路径）
- [ ] 3.2 workflow validate 递归加载 demand 时复用同一 roots 集合（确保边界一致；避免“入口校验了但子加载没校验”）
- [ ] 3.3 单测：workflow `runs[*].demand` 的 `../`、绝对路径（越界）与 alias（越界）在默认 roots 下 fail-fast；在 roots 覆盖后允许

## 4. symlink 逃逸回归

- [ ] 4.1 新增测试夹具：root 内 symlink 指向 root 外的 `.yaml` 文件
- [ ] 4.2 默认策略下该用例必须 fail-fast（错误信息包含 resolved path + roots）

## 5. Final Gates

- [ ] 5.1 运行 `just openspec-check` 确保 OpenSpec 工件通过校验
- [ ] 5.2 运行 `just qa`（或最小子集）确保无 lint/test 回归
