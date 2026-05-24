---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate tools-resources-discovery --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "tools-resources-discovery"
purpose: "定义面向用户的稳定公开入口,用于从 output root 定位“最新一次成功发布”的产物集合(books/files),并隐藏底层 D-2 版本化输出协议的内部落盘细节."
requirements[3]{req_id,title,statement}:
  r1,system MUST provide a stable facade to discover the latest published output reso,"系统 MUST 提供一个面向用户的稳定公开入口(建议入口 package `scalim.shortcuts.resources`,v1 子域模块为 `scalim.shortcuts.resources.outputs`),用于从某个 output root 定位“最新一次成功发布”的产物集合。 该 facade 的目标是隐藏底层落盘协议细节(D-2 版本化输出的 `versions/` 目录与 `manifest/*.json`),避免下游手写 JSON 读取与路径拼接逻辑。 备注(非约束): `scalim.shortcuts.resources` 被视为资源类 shortcut 的长期统一入口；本轮 v1 仅新增 `scalim.shortcuts.resources.outputs`（从 output root 发现最新 outputs(books/files)）这一最小切片,其它 input artifacts / ctx resources 等能力后续再增补。 最小能力: - 输入 MUST 为 output root（目录路径,`str` 或 `pathlib.Path` 均可）。 - 输出 MUST 为一个可直接使用的产物快照对象(例如 `LatestOutputs`),其中包含: - `run_id: str`（稳定标识符;用于诊断与追踪,但不以 “version” 术语对外表达） - `books: Mapping[str, Path]`（book_id → 产物路径） - `files: Mapping[str, Path]`（file_id → 产物路径） - 用户侧 MUST NOT 需要自行读取 `manifest/latest.json` 或拼接 `versions/<id>` 路径。"
  r2,"facade MUST support both fail-fast and optional discovery modes","系统 MUST 同时支持: - fail-fast: 当 output root 下不存在最新指示或无法解析时,调用 MUST 失败并提供可诊断错误信息（包含 root 与失败原因）。 - optional: 提供 `try_*`（或等价）API,在缺失最新指示时返回 `None`（而不是抛出异常）。"
  r3,"facade MUST provide id-based shortcuts without exposing internal layout","系统 MUST 提供常用快捷方法以减少调用方样板代码: - 通过 `book_id` 获取最新 workbook 路径 - 通过 `file_id` 获取最新 file 路径 这些快捷方法 MUST 只要求 `output_root + artifact_id` 作为输入,且 MUST 不要求调用方了解内部目录结构。"
scenarios[6]{req_id,id,given,when,then}:
  r1,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r1,"user-locates-latest-workbook-and-csv-by-stable-facade",某 output root 下存在一份已发布的 outputs（包含至少一个 `book_id` 或 `file_id`）,用户调用 `scalim.shortcuts.resources.outputs` 的 “load latest outputs” facade,系统 MUST 返回包含可直接使用 `Path` 的快照对象
  r2,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r2,"missing-latest-pointer-can-be-handled-explicitly",某 output root 下不存在“latest outputs”指示（例如没有产物或产物被跳过）,用户调用 optional discovery API,系统 MUST 返回 `None`
  r3,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r3,"shortcuts-return-resolved-paths",某 output root 的最新快照包含 `book_id=report` 与 `file_id=detail_csv`,用户调用 “latest book/file path” 快捷方法,系统 MUST 返回对应产物的可直接使用路径
```
