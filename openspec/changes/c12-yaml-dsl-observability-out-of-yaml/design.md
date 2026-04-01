## Context

`observability.*` 的问题不只是“字段多”,而是它本质上已经成为运行入口的集成配置:

- 是否启用日志 / 诊断 / 可视化
- 观测输出格式与 payload policy
- 运行时路径/文件产物
- 用户自定义 hook / observer / 内部监控体系

这些都与环境、组织约束、排障策略高度绑定,并不属于 demand/workflow 的业务建模本体。

## Goals

- 明确 `observability.*` 不再属于 YAML 主线 authoring surface
- 给 Python/CLI 侧的承载模型一个明确边界
- 减少 schema/imports/LSP 的非核心负担

## Non-Goals

- 不重写 observability framework
- 不定义最终 CLI 参数细节

## Design Direction

### 1. `observability.*` 统一视为 runtime integration surface

本提案的最终方向是直接把整组配置迁出 YAML,而不是继续在 YAML 中保留一个“精简版”:

- 这类配置高度环境相关
- 用户很可能需要注入自己的 hook / observer / metrics sink
- 留在 YAML 里只会继续制造重复建模

### 2. 不保留 YAML profile 壳

对 observability 而言,连一个很薄的 YAML profile 壳都不太值得保留:

- profile 仍会让 authoring surface 带上控制面色彩
- 用户最终还是得在 Python/CLI 入口拼接真实组件

因此本 change 的结论是“直接迁出”,而不是“迁出大部分但留 profile 引用”。

### 3. 错误信息要直接给迁移路径

当 YAML 中出现 `observability.*`,建议报错直接提示:

- Python `run(..., components=.../overrides=...)`
- 对应 CLI 入口参数

避免只报“unknown field”而不给迁移方向。

## Resolutions From Review

### 1. 过渡策略: 对已知的 `observability.*` 迁移项采用一次性 warning,而不是立即 fail-fast

当前结论是:

- 在过渡期内,对 **已知且可识别的** `observability.*` 旧字段发出一次性 migration warning
- warning 应明确说明:
  - 该 key 将被忽略
  - 推荐迁移到 Python / CLI 的哪个入口

这里不建议把所有 unknown key 都一律降级成“warning + 忽略”,否则会把普通拼写错误、真实坏配置也吞掉。

更稳妥的方式是:

- 普通 unknown key 继续按现有 unknown-field 规则处理
- 已知的 observability 迁移项单独走一层 deprecation / migration warning

### 2. 文档改造不只限于 API 文档,还要覆盖 skills / notebooks / 示例材料

当前结论是:

- 需要同步调整 docs
- 需要同步调整 skills
- 需要同步调整 notebooks / fixtures / 示例

否则用户虽然看到 YAML 不推荐写 `observability.*`,但仓库里的配套材料仍会继续误导用法。


## Dependencies

- 本 change 与 `c999-yaml-dsl-lsp` 的 editor semantics 补充无强实现耦合,可独立审批
- demand imports scope 收敛应以前者结果为前提: `observability.*` 迁出后,imports scope 也不再覆盖这一区域
