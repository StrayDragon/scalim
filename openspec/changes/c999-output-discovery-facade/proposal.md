## Why

当前版本化输出(D-2)通过 `<root>/manifest/latest.json` + `<root>/versions/<id>/manifest.json` 提供“稳定入口”,但下游(服务端/脚本/测试/agent skill)
往往不得不手写 `json.loads((root / "manifest" / "latest.json").read_text(...))` 以及路径拼接逻辑。

这会把内部落盘形状(`versions/`、manifest 文件名等)扩散成事实公共契约,并增加未来重构成本:只要内部目录结构或 manifest 字段调整,用户代码就会被迫迁移。

我们需要一个 **面向用户的稳定 facade/shortcut** 来表达“从 output root 定位最新一次运行的产物”,隐藏 versioned 的内部概念,并纳入 public API 治理与回归(文档 + notebooks suite)。

另外,模块命名需要避免与既有 `sinks` / `outputs` 术语混淆,并减少未来扩展时的“语义漂移”。本提案倾向采用更通用的 shortcut 入口:

- 推荐入口: `scalim.shortcuts.resources`

## What Changes

- 新增一个稳定公开入口 package(建议 `scalim.shortcuts.resources`;v1 子域模块为 `scalim.shortcuts.resources.outputs`): 提供“产物/资源发现与定位”API,输入为 output root,输出为可直接使用的产物路径映射。
  - API 不暴露 `versions/`、`manifest/latest.json` 等内部细节,避免用户手写 JSON 与路径拼接。
  - API MUST 覆盖 workbook/books 与 files 两类产物的最小闭环,并提供常用快捷方法(例如按 `book_id/file_id` 取 path)。
- 更新用户材料(文档/skills/notebooks)的推荐写法:
  - public API 文档与 marimo public API suite 增加对该 facade 的介绍与回归覆盖。
  - YAML DSL 的版本化输出 reference/示例改为使用 facade(不再直接读 `latest.json`)。
- 保持现有 D-2 协议与实现不变: `workflow-versioned-outputs` 仍是底层协议 SSOT；新 facade 只是对外稳定入口。

## Capabilities

### New Capabilities
- `resources-discovery`: 提供稳定公开的“资源发现/最新产物定位”facade,隐藏 D-2 的内部落盘细节。

### Modified Capabilities
- `public-api-surface-governance`: 将新的 facade 模块纳入 curated entrypoints,并要求用户材料优先使用该入口而不是内部落盘细节。
- `marimo-example-public-api-suite`: public API suite 增加对新 facade 的章节覆盖,并与 curated public surface 保持一致。

## Impact

- 新增公共模块与符号集合(需 `__all__` 显式治理),并纳入 public API suite 回归。
- docs/skills/notebooks 的示例将减少对 `manifest/latest.json` 的手写读取,降低下游迁移成本。
- 未来若调整 D-2 内部布局或 manifest 字段,只要保持 facade 契约不变,用户侧无需修改导入与调用方式。
