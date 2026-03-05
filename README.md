<p align="center">
  <img src="docs/assets/logo.svg" alt="logo" width="100%">
</p>

| - | - |
| --- | --- |
| 库分发 | [![PyPI version](https://img.shields.io/pypi/v/scalim?logo=pypi&logoColor=white&style=flat-square)](https://pypi.org/project/scalim/) [![Python versions](https://img.shields.io/pypi/pyversions/scalim?logo=python&logoColor=white&style=flat-square)](https://pypi.org/project/scalim/) |
| 文档生成器 | [![Zensical](https://img.shields.io/badge/docs-Zensical-526CFE?style=flat-square)](https://zensical.org/docs/) |
| 项目工具 | [![uv](https://img.shields.io/badge/uv-managed-6A2C70?logo=uv&logoColor=white&style=flat-square)](https://github.com/astral-sh/uv) [![ruff](https://img.shields.io/badge/ruff-linted-D7FF64?logo=ruff&logoColor=111111&style=flat-square)](https://github.com/astral-sh/ruff) [![basedpyright](https://img.shields.io/badge/basedpyright-checked-3B82F6?style=flat-square)](https://github.com/DetachHead/basedpyright) [![pnpm](https://img.shields.io/badge/pnpm-workspace-F69220?logo=pnpm&logoColor=white&style=flat-square)](https://pnpm.io/) |
| 前端 | [![Svelte](https://img.shields.io/badge/Svelte-frontend-FF3E00?logo=svelte&logoColor=white&style=flat-square)](https://svelte.dev/) [![Vite](https://img.shields.io/badge/Vite-built-646CFF?logo=vite&logoColor=white&style=flat-square)](https://vite.dev/) |
| AI | [![Codex](https://img.shields.io/badge/Codex-used-111111?style=flat-square)](https://github.com/openai/codex) [![Claude](https://img.shields.io/badge/Claude-used-D97757?logo=claude&logoColor=white&style=flat-square)](https://www.anthropic.com/claude) [![Cursor](https://img.shields.io/badge/Cursor-used-111111?logo=cursor&logoColor=white&style=flat-square)](https://cursor.com/) |

Scalim 是一个把字段依赖、关系加载和执行计划放在同一层建模的数据编排框架:可以直接用 Python 写,也可以用 YAML DSL 配置,适合把报表和数据计算流程整理得更清楚,也更容易控制内存和执行成本.

## 主要特性

- 内置字段剪枝、字段释放和行级释放,尽量只保留当前批次真正还要用的数据,减少上下文占用(内存占用), 支持多种并行模式
- 支持直接用 `Python` 描述计算逻辑,也支持用 `YAML DSL` 写配置, 配套可视化编辑器, `json schema` 校验和 `CLI` 工具, 写配置时更容易补全、检查和落地
- 支持批量执行、流式输出和行式/列式 sink,方便在吞吐、内存和输出形式之间做取舍
- 支持 [agent skill](./artifacts/skills/) 集成
- 有可视化在线工具做回放和排查,执行计划、事件流和 trace 都能接起来看

更多见 [docs/doc/index.md]