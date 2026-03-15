**状态: TODO**

## 4. ANALYZE Pipeline (extensions.analyze)

- [ ] 4.1 定义 analyzer contract + 结果结构(issues + optional meta):
  - 建议新增模块: `src/scalim/dsl/by_yaml/runtime/extensions/analyze.py`(或等价位置),定义:
    - analyzer 输入上下文(至少含 `yaml_path` + stage + `ExtensionHost.summary`)
    - issue 数据结构(字段集合一次性定型;见 design.md)
    - analyzer 返回值形态(issues + 可选 meta)
- [ ] 4.2 决定 analyzer 执行阶段并接入 extensions-aware 编译管线:
  - raw stage(imports 展开后、validator 前): 执行 raw analyzers
  - compiled stage(可选;已有 config/IR/request 后): 执行 compiled analyzers
  - analyzer 执行仅在 `--resolve-extensions` 模式下发生
- [ ] 4.3 将 analyzer issues 合并到校验输出:
  - CLI 文本输出: 区分 core validator issues vs extensions analyzer issues(至少在渲染上可识别来源)
  - `--json` 输出: 增加 `extensions_errors/extensions_warnings` 字段
- [ ] 4.4 回归测试:
  - `tests/fixtures/extensions_analyze_mod.py` 提供可 allowlist 引用的 analyzer:
    - 产出 warning/error(带 path/message/code 可选)
    - 可选: 故意抛错以测试 analyzer_failure 策略
  - `tests/test_yaml_dsl_extensions_analyze_cli.py` 覆盖:
    - 未启用 resolve 时 analyzer 不执行
    - 启用 resolve 后 issues 出现在输出中(含 ref/stage)

## 10. CLI, Docs, Examples, QA Gates

- [ ] 10.1 CLI 增强(显式 resolve + allowlist + analyze):
  - 修改 `src/scalim/cli/yaml_dsl.py`:
    - `yaml-dsl validate` 增加 `--resolve-extensions`
    - 增加 allowlist flags: `--allow-module/--allow-function`(可重复)
    - 增加 `--trusted` 快捷参数(等价通配 allowlist)并输出风险提示
    - 新增 `yaml-dsl analyze` 子命令(输出结构化分析报告;支持 `--json`)
- [ ] 10.1.1 allowlist 治理:
  - `--resolve-extensions` 模式下未提供 allowlist 时 MUST fail-fast 并提示补齐(或使用 `--trusted`)
- [ ] 10.1.2 默认 validate 的可行动提示:
  - 当检测到扩展语法(例如存在 `extensions` 块,或出现 custom `container.type`/`aggregate.kind/ref`)但未开启 `--resolve-extensions` 时:
    - 文本输出提示“当前为未解析 extensions 的校验模式”
    - 提示如何开启 resolve + allowlist
- [ ] 10.2 文档与示例:
  - 新增 `docs/doc/yaml-dsl/extensions.md`(extensions quickstart + 安全边界 + 常见模式)
  - 在 `docs/doc/yaml-dsl/index.md` 增加入口链接
  - 增加一个完整示例(推荐放在 `docs/doc/yaml-dsl/examples/` 或等价位置): BUNDLE + ANALYZE + direct config
- [ ] 10.3 如 authoring surface 有变更,更新 canonical demo YAML(若仓库内存在 SSOT demo 文件,以其为准)
- [ ] 10.4 Run `just gen-docs` 并确认 injected blocks/schema mirrors 一致
- [ ] 10.5 Run `just qa` 与 `just openspec-check`
