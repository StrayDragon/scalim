## Why

当前 scalim 的错误/异常体系缺少统一规范:不同模块混用 `ValueError`/`TypeError`/`RuntimeError` 以及零散的自定义异常类,错误信息口径不一致(是否包含 code/context、是否泄露敏感信息、是否给出迁移提示等),导致用户排障成本高、测试断言脆弱且跨模块行为难以稳定演进。

## What Changes

- 引入一套明确的“用户可感知错误”规范:错误分类、异常基类/派生约定、稳定的错误码与可选 context/hint 结构、错误信息的敏感信息治理与格式约定。
- 明确各类错误的抛出边界与传播策略(配置错误/输入不合法/运行时护栏违规/系统错误/第三方依赖错误等)。
- 定义渐进迁移策略:允许先在新代码/新路径使用新体系,再逐步迁移存量错误点,并提供可测试的验收口径。

## Capabilities

### New Capabilities
- `error-taxonomy`: 统一 scalim 的错误/异常体系,包括错误分类、错误码、异常类型约定、错误信息治理与迁移/测试口径。

### Modified Capabilities
- (none)

## Impact

- 代码: 影响范围横跨 `src/scalim/`(execution/dsl/workflow/ob/hooks/utils 等)的错误抛出点与异常类型定义;需要逐步迁移以保持可控。
- 测试: 需要将“匹配原始错误 message”的断言逐步迁移为“匹配稳定错误码/类别/关键字段”的断言,降低脆弱性。
- 文档治理: 规范作为 OpenSpec SSOT 写入 `openspec/specs/**`;如需要同步到 docs-site,遵循生成物/注入区块规则,入口为 `just gen-docs`(不手改任何 `.gen.` 文件与 `BEGIN/END AUTOGEN` 区块内部)。

