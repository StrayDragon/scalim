## Why

extensions 引入后,validate/analyze 会触达用户提供的 Python 引用。
为避免校验命令隐式执行用户代码,CLI 必须提供显式开关与 allowlist 边界,并为 CI/IDE 提供可消费的结构化分析输出。

## What Changes

- 定义 analyzer contract + 结构化 issues 输出(shape 一次性定型)
- 决定 analyzer 执行阶段(raw/compiled)并接入 compiler/validator/CLI
- CLI:
  - 默认 `yaml-dsl validate` 不解析/执行 extensions
  - 当检测到扩展语法时输出可行动提示
  - `--resolve-extensions` 显式开启解析/执行
  - allowlist flags + `--trusted` 快捷参数
  - `yaml-dsl analyze` 输出结构化分析报告(含 ExtensionHost.summary)
- docs: extensions quickstart + 完整示例(BUNDLE/ANALYZE/direct config)

## Capabilities

### Modified Capabilities

- `yaml-dsl-cli-validation`
- `yaml-dsl-extensions`

## Impact

- 影响 CLI 与诊断输出: `src/scalim/cli/yaml_dsl.py` 等

## Dependencies

- 依赖 `yaml-dsl-extensions-host-core`: analyzers 由 `ExtensionHost` 解析/合并得到
- 依赖 `yaml-dsl-extensions-schema`: schema/loader 需要先能承载 `extensions.analyze`
- 依赖 `yaml-dsl-extensions-transformers`: extensions-aware 管线需要能在 raw/compiled 阶段执行 analyzers 且不破坏 validator 默认路径
