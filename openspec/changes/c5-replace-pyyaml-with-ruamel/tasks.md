## 1. OpenSpec 与手工 SSOT 调整

- [ ] 1.1 对齐本 change 的 OpenSpec 工件(proposal/design/specs/tasks),明确“一步到位迁移到 vendored ruamel.yaml + YAML 1.2 + rt 编辑门禁”。
- [ ] 1.2 更新 vendors 运行时相关的手工 SSOT,至少覆盖 `src/scalim/vendor/README.md` 与 `src/scalim/vendor/yamlx/SOURCE.md`,说明默认 backend 已切换为 ruamel,PyYAML 仅保留为 vendored 源码/审计用途。
- [ ] 1.3 运行 `just openspec-check` 校验 OpenSpec 工件(注意: `.gen.*` 与 `BEGIN/END AUTOGEN` 注入区块不得手改)。

## 2. 运行时默认 backend 切换(ruamel safe + YAML 1.2)

- [ ] 2.1 将统一 YAML loader(`src/scalim/dsl/by_yaml/_internal/config_parsing/yaml_load.py`)内部实现切换为 vendored `ruamel.yaml` 的 safe 解析,并显式启用 YAML 1.2 语义边界。
- [ ] 2.2 保持并锁定现有 duplicate key 策略与错误结构:
  - 默认开启检测,重复键报错且包含 `loc`
  - 显式关闭检测时,重复键允许且语义为 last-wins
- [ ] 2.3 将 demand/workflow/CLI validate/imports/project-config/effective-yaml dump 等所有入口收敛到统一 loader,避免分散的第三方 parser 调用。
- [ ] 2.4 确保 vendors-sync 下运行时不依赖外部安装包(`yaml`/`ruamel.yaml`),仅依赖 `src/scalim/vendor/yamlx/` 的 vendored 实现。

## 3. Round-trip 编辑(ruamel `typ=\"rt\"`)与稳定性门禁

- [ ] 3.1 将 `yaml-dsl upsert-lsp-comment` 的写入实现切换为基于 vendored `ruamel.yaml` 的 round-trip(`typ=\"rt\"`),保留注释/格式/anchors。
- [ ] 3.2 引入并通过两类门禁:
  - no-op round-trip(`load` 后立刻 `dump`) MUST 字节级完全一致
  - upsert 仅允许修改 schema modeline 所在行,不得无意义重排正文
- [ ] 3.3 选定 canonical YAML 文件作为黄金样本(覆盖 anchors/注释/缩进/序列等关键结构),并用测试锁定。

## 4. 回归与 py36 门禁(含 TUNA mirror)

- [ ] 4.1 增补 corpus 回归:对 `tests/fixtures/*.yaml` 与 `notebooks/marimo/**/declared_yaml_dsl/*.yaml` 执行 ruamel 解析回归,并提供 ruamel vs vendored PyYAML 的对拍测试(迁移期风险控制)。
- [ ] 4.2 在真实 Python 3.6 环境中补充 vendored import / parse / duplicate key / parse error smoke checks;若通过 docker 验证,安装依赖时使用大陆 pypi TUNA mirror。
- [ ] 4.3 运行 targeted pytest 与 `just qa`(或相关子集)完成验收,并记录已知 BREAKING 语义边界(YAML 1.2 标量解析)。

## 5. 文档生成(仅在需要时)

- [ ] 5.1 仅当实现影响 docs/specs 生成物或注入区块时,从对应 SSOT 运行 `just gen-docs` 刷新生成内容;不得手改 `.gen.*` 文件或受控注入区块。
