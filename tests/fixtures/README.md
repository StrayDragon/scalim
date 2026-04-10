# `tests/fixtures/` 约定（fixtures / snapshots）

本目录用于存放测试的 **SSOT fixtures**（可被提交与 review），包含：

- 被 YAML 字符串引用的最小 Python 模块/函数（例如用于 `python:` 引用或 imports 场景的测试替身）。
- 各类场景输入文件（YAML/JSON/文本等）。
- **contract tests** 的 golden **snapshots**（稳定、可序列化的输出对拍基线）。

## 目录边界

- `tests/fixtures/`：可被 YAML 字符串引用的素材与最小 Python 模块（允许被 `import`/`python:` 引用）。
- `tests/support/`：测试 harness/工具代码（仅供 Python `import` 使用），**不得**被 YAML 字符串引用（对应 tests-domain-suites 的边界约束）。

## 推荐结构

当某类 contract suite 需要按“场景”组织输入与快照时，推荐结构如下：

- `tests/fixtures/<suite>/<scenario>/...`：该场景的输入文件（YAML/JSON/…）
- `tests/fixtures/<suite>/<scenario>/snapshots/*.json`：该场景的输出快照（golden）

其中：

- `<suite>`：面向一个 contract suite 的名称（例如 `yaml_dsl_lsp_contract`）。
- `<scenario>`：最小可复现的业务/协议场景（例如 `imports_basic`、`python_reference`）。

## Snapshots（golden）约定

- 快照文件格式：JSON（便于稳定化、排序、normalize）。
- 必须包含顶层字段 `schema_version`（整数），用于未来演进与回放兼容。
- 默认运行只做对拍（diff 失败即失败），**不允许隐式更新**。

推荐快照 JSON 外形（示例）：

```json
{
  "schema_version": 1,
  "snapshot": {
    "kind": "example",
    "data": {}
  }
}
```

## 更新流程（显式）

当且仅当出现以下情况才允许更新快照：

- 需求/规范明确变更并已在 PR 中说明；
- 或确认修复 bug 后更新快照基线。

更新必须显式开启：

- `UPDATE_GOLDEN=1 <pytest command>`

无该环境变量时，测试必须保证不会改写任何 snapshot 文件。

