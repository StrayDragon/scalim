## 1. CLI runner（YAML-first 闭环）

- [ ] 1.1 在 `src/scalim/cli/yaml_dsl.py` 增加 `yaml-dsl run` 子命令（参数解析 + 退出码约定 + 最小日志输出）
- [ ] 1.2 在 `src/scalim/cli/yaml_dsl.py` 增加 `yaml-dsl workflow run` 子命令（复用 `scalim.dsl.by_yaml.run_workflow`）
- [ ] 1.3 支持 `--init-vars-json`（JSON mapping → `init_vars`）并在缺失/类型不合法时 fail-fast 给出可操作错误
- [ ] 1.4 支持 `--allowed-module/--allowed-function`（可重复）并保持 allowlist 为空时 fail-fast（不引入隐式 trusted 模式）
- [ ] 1.5 支持 `--allowed-yaml-root`（可重复）并透传到 by_yaml runtime（与 validate 保持一致口径）

## 2. `scalim.yaml` runner defaults（schema + discovery + 合并规则）

- [ ] 2.1 扩展 `src/scalim/dsl/by_yaml/_internal/config_parsing/project_config.py`：解析 `yaml_dsl.runner.*`（保持 nearest-wins discovery 不变）
- [ ] 2.2 扩展 scalim.yaml schema SSOT（`src/scalim/dsl/by_yaml/schema_dsl/**`）覆盖 `yaml_dsl.runner.*`
- [ ] 2.3 运行并提交生成物（生成物为 SSOT 产物,禁止手改）：
  - [ ] 2.3.1 运行 `just gen-yaml-dsl-schema` 更新 `src/scalim/dsl/by_yaml/schema/scalim_yaml.gen.json`
  - [ ] 2.3.2 以 drift gate 验收（`just qa` 或对应 schema drift check）
- [ ] 2.4 CLI runner 合并规则落地：CLI flags > `scalim.yaml` runner defaults > fail-fast（并在错误信息中说明来源与覆盖方式）

## 3. Python API 收敛（options-object 唯一入口，breaking）

- [ ] 3.1 将 `src/scalim/dsl/by_yaml/runtime/entrypoints.py` 的 `run/compile` 收敛为 `options: RunOptions` 形态
- [ ] 3.2 新增 `src/scalim/dsl/by_yaml/legacy_entrypoints.py`（或等价内部模块）保留旧长签名入口供过渡/内部回归使用（不纳入推荐导入）
- [ ] 3.3 更新 `src/scalim/dsl/by_yaml/__init__.py` 的门面导出（`__all__`）：
  - [ ] 3.3.1 导出 `RunOptions`
  - [ ] 3.3.2 保持 `RunOverrides/Compilation/RunResult/run/compile/run_workflow` 等稳定符号仍可导入
- [ ] 3.4 更新与 public API 相关的示例/回归（以代码实现为准）：
  - [ ] 3.4.1 notebooks: `notebooks/marimo/example_public_api_suite/chapters/ch130_public_api_dsl_by_yaml.py`
  - [ ] 3.4.2 docs: `docs/doc/getting-started/public-api.md` 与 YAML 用户指南中的 run 示例

## 4. 文档与示例对齐（以实现为事实来源）

- [ ] 4.1 全面扫描 docs/notebooks/skills 中对 `scalim.dsl.by_yaml.run/compile` 的调用示例,升级到 options-object 新写法
- [ ] 4.2 若涉及生成页或注入区块：
  - [ ] 4.2.1 明确 SSOT（手写源文件/脚本）与生成物（`*.gen.*`/AUTOGEN 区块）
  - [ ] 4.2.2 运行 `just gen-docs` 刷新生成页/注入区块（禁止手工改生成物）

## 5. 测试与验收

- [ ] 5.1 为 CLI runner 添加最小 e2e 测试（成功路径 + allowlist 缺失 fail-fast 路径）
- [ ] 5.2 更新/新增回归覆盖：确保 options-object 入口与 CLI runner 走同一条编译/执行主链路
- [ ] 5.3 运行质量门禁：
  - [ ] 5.3.1 `python3 scripts/check-api-surface-governance.py --check`
  - [ ] 5.3.2 `python3 scripts/check-user-material-import-boundaries.py --check`
  - [ ] 5.3.3 `just openspec-check`
  - [ ] 5.3.4 `just qa`
