# 仓库开发约定

??? note "适用读者"
    - 项目贡献者(开发/测试/发布前的边界约束)
    - 需要在仓库内协作开发的使用方开发者

这页汇总本仓库的约定与常用入口,帮助你快速对齐边界与流程.

## 1. Python 版本边界(务必先看)

这里有一个**需要明确区分的版本边界**:

- 运行时目标: `src/scalim/` 代码需要兼容 Python 3.6
- 开发/测试环境: 以 Python 3.10+ 为主, `uv` 的 `dev` dependency group 也显式要求 `>=3.10`
- 发布元数据: `pyproject.toml` 的 `requires-python = ">=3.6"`, 以保证发布到 PyPI 的 wheel 可以被 Python 3.6 安装
- 兼容性验证: `uv` 本身不接受 Python 3.6 解释器做 `sync/run`，因此 3.6 安装验证使用独立 `venv + pip` 进行

所以写 `src/scalim/` 里的代码时,不要使用仅 3.7+ 才有的语法/标准库行为.

## 2. 项目结构与 import 约定

- `src/scalim/` 会被外部直接 import 使用
  - 在 `src/scalim/` 内优先使用相对导入
  - 严禁在 `src/scalim/` 内写 `import scalim` 或 `from scalim...`
- `src/scalim/` 之外(例如 `tests/`、`scripts/`、`notebooks/`)可以直接 `import scalim` 方便调试
- `src/scalim/` 下避免新增与 Python 标准库同名的模块文件(例如 `types.py`、`inspect.py`)
- 面向普通用户/文档/示例时,建议优先使用官方入口(受控导出面),避免误用内部实现路径:
  - `scalim.dsl.by_yaml`: YAML DSL 官方入口(运行入口 + 运行期契约)
  - `scalim.spec.ir`: IR 类型官方入口
  - `scalim.planning`: 规划层入口
  - `scalim.execution`: 执行层入口
  - `scalim.ob`: 可观测性入口
  - 仅当官方入口未导出需要的符号时,才从子模块显式导入(并避免依赖 `_internal` 等实现细节)

## 3. 常用命令(开发侧)

日常工作流:

```bash
uv sync --dev --frozen
just test
```

更多命令入口见: [开发](index.md)

## 4. YAML DSL schema 生成物维护

如果你修改了 `src/scalim/dsl/by_yaml/schema_dsl/`(models/constants/builder 等),需要同步更新生成物:

```bash
just gen-yaml-dsl-schema
```

并提交:

- `src/scalim/dsl/by_yaml/schema/demand.gen.json`

另外 `just check`/`just qa` 会做 drift 检查,未提交生成物会直接失败.

## 5. 示例文档维护

如果你改了 `notebooks/marimo/examples/demo_big_data_report/demo_*.py` 的文件名、增删示例或调整学习路径,需要同步更新:

- `notebooks/marimo/examples/README.md`

默认的非 bench 测试会校验 README 里引用的 demo 路径是否存在,用来防止文档漂移.

## 6. by_yaml runtime 模块改名(迁移提示)

- `scalim.dsl.by_yaml.runtime.types` → `scalim.dsl.by_yaml.runtime.contracts`
- `scalim.dsl.by_yaml.runtime.inspect` → `scalim.dsl.by_yaml.runtime.introspection`

## 7. YAML DSL 入口(用户侧)

如果你要写/跑 YAML 配置,优先看:

- [YAML DSL](../yaml-dsl/index.md)

其中包含:

- 语法总览(以 schema + validator 为准)
- 编辑器与 schema 同步
- CLI 校验命令与运行入口

## 8. 学习入口(示例)

在本目录安装依赖后,可以用 marimo 打开 Workspace 的交互式笔记本:

```bash
uv run marimo edit
```
