## Context

`src/scalim/dsl/yaml_dsl/` 中异常包装使用 `from exc`（~44 处）和 `from None`（~16 处）两种风格混用。`from None` 会设置 `__cause__ = None` 并抑制 `__context__`，使 traceback 中的 "During handling of the above exception, another exception occurred" 链消失。

两种风格各有适用场景：
- `from exc`：保留完整诊断链，适合内部错误传播。
- `from None`：隐藏实现细节，适合公共 API 边界。

当前问题是缺乏明确规范，导致使用不一致。

约束：
- 不改变异常类型或消息
- 保持 Python 3.6 兼容（`from exc` / `from None` 语法 3.0+ 可用）

## Goals / Non-Goals

**Goals:**
- 制定异常链规范并记录
- 修复不合理的 `from None` 使用
- 可选：添加治理机制

**Non-Goals:**
- 不改变异常类/层次结构
- 不做异常消息模板化（那是另一个变更）

## Decisions

### 1) 规范：默认 `from exc`，公共 API 边界允许 `from None`

- `src/scalim/` 内部模块间传播：`from exc`（默认）。
- 仅在以下场景允许 `from None`：
  - YAML 加载边界（`yaml_load.py`）：用户不需要看到 ruamel 内部异常。
  - JSON Schema 验证边界：用户不需要看到 jsonschema 内部栈。
- 每个 `from None` 必须带注释说明原因。

### 2) 修复范围

按审查结果，以下 `from None` 应改为 `from exc`：
- `workflow_compile.py`：4 处（内部 ValueError/TypeError → ScalimWorkflowConfigError，原始异常对调试有价值）
- `workflow_config/_parse.py`：2 处（同上）
- `project_config.py`：2 处（TypeError 包装，原因信息有诊断价值）
- `loader.py`：2 处（内部异常包装）
- `output_composition_yaml.py`：1 处（ValueError 包装）

保留 `from None` 的（加注释）：
- `yaml_load.py`：2 处（YAML 解析边界，隐藏 ruamel 内部）
- `conversion_sources.py`：1 处（审查后决定是否保留）

### 3) 治理（可选）

暂不添加自动化 lint——`from None` 是合法 Python 且有适用场景。通过 code review 规范执行。

## Risks / Trade-offs

- 用户的 traceback 输出会变长（包含 cause chain）。这是改善，不是退化。
- 极少数情况下可能暴露内部模块名（可接受，这些是开发者错误场景）。

## Migration Plan

- 按文件逐一修复 `from None` → `from exc`
- 为保留的 `from None` 添加 `# suppress chain: <reason>` 注释
- 验证：`just qa`

## Open Questions

- 无。
