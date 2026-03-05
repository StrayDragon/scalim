---
name: scalim-yaml-dsl
description: "Scalim YAML DSL 使用与排错指南,涵盖 sources/fields/relations/output 等配置. 触发词: scalim dsl, scalim yaml dsl, scalim config, 使用 scalim 框架 yaml dsl 编写需求"
---

# Scalim YAML DSL

## 使用说明
- 使用 `references/dsl-reference.md` 获取字段/枚举完整说明.
- 使用 `references/example-full/README.md` 了解 loader、约束与完整示例.
- 示例仅存放在 `references/example-full/`
- 校验 YAML(完整): `uv run scalim-cli yaml-dsl validate <file.yaml>`.
- 校验 YAML(schema-only): `uv run scalim-cli yaml-dsl schema validate <file.yaml>`.
- Schema 查询: `scalim-cli yaml-dsl schema show` / `scalim-cli yaml-dsl schema path`.
- 安装(推荐): `uv tool install /path/to/scalim[cli]`.
- 安装(备选): `pip install --user /path/to/scalim[cli]`.

## 适用场景
- 编写或修改 Scalim YAML DSL 配置.
- 基于 schema/validator 做配置校验.
- 排查 loader、relations 或字段映射错误.

## 能力范围
- 提供完整 schema 与字段/枚举说明.
- 提供完整可运行示例与真实 loader.
- 提供校验命令指引(完整 + schema-only).

## 限制
- 不直接执行 Scalim 任务,仅提供指引与参考.
- 示例集保持最小化(仅一个完整示例).

## 参考文档
- `references/dsl-reference.md` - 字段/枚举完整说明.
- `references/example-full/README.md` - 完整示例说明(含 loader 与约束).
- `references/example-full/ecommerce_report.yaml` - 完整 YAML 配置示例.

顶层字段:
- `name`
- `_templates`
- `description`
- `batch_size`
- `retry`
- `main_source`
- `sources`
- `fields`
- `relations`
- `guardrails`
- `output`
- `observability`
