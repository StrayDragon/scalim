# Runtime Troubleshooting

## 何时读取

- YAML 使用了相对引用(例如 `..loaders:fn`),但在服务端运行时报错:
  - `无法根据 yaml_path='...' 推导 base_module_path: 目录 '...' 不在任何 sys.path 条目下`
- 同一份 YAML 在本地脚本可运行,但在 `Django/WSGI/ASGI/gunicorn/systemd/crontab` 等环境不可运行
- 你需要解释“为什么重构前能跑/重构后不能跑”,但怀疑点在启动方式而非 Scalim 本身

## 背景: 为什么相对引用依赖 `sys.path`

相对引用的归一化并不是“文件系统相对路径 import”,而是基于 Python import 体系:

- 以 `yaml_path` 的目录(`yaml_dir`)为基准
- 遍历 `sys.path` 找到能覆盖 `yaml_dir` 的 import root(即 `yaml_dir` 在某个 `sys.path` 条目下面)
- 将 `yaml_dir` 相对该 import root 的目录段用 `.` 拼接成 `base_module_path`
- 再用 `base_module_path` 把 `..loaders:fn` 归一化为绝对模块引用,然后做 allowlist 校验 + import

因此:

- `cwd` 变化 + `PYTHONPATH` 里用了相对路径(例如 `PYTHONPATH=INTEGRATION_APP:INTEGRATION_APP/INTEGRATION_APP`) 会导致 `sys.path` 解析到错误的位置
- 进程启动目录在 `/tmp`、`/srv/app`、容器工作目录等场景下,可能本地脚本“看起来一样”的命令在服务端完全不同

## 推荐: 服务启动阶段做一次 fail-fast 自检

目标是把问题从“线上某个 API 第一次被打到才报错”提前到“服务启动就报错”,并给出更明确的上下文日志。

```python
import os

from scalim.dsl.yaml_dsl.tools import derive_base_module_path

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
yaml_path = os.path.join(THIS_DIR, "path", "to", "demand.yaml")
print("[scalim] base_module_path =", derive_base_module_path(yaml_path))
```

如果这里报错 `... 目录 '<yaml_dir>' 不在任何 sys.path 条目下 ...`,说明:

- demand YAML 所在目录不在任何 import root 下面(即 `sys.path` 没包含包根目录)
- 此时相对引用无法被归一化为可 import 的模块路径,所以 Scalim 选择 fail-fast

## 常见修复策略

### 1) 用绝对路径写 `PYTHONPATH`(推荐)

生产环境建议避免依赖 `cwd`,改为显式绝对路径:

- `PYTHONPATH=/abs/repo/INTEGRATION_APP:/abs/repo/INTEGRATION_APP/INTEGRATION_APP:...`

### 2) systemd / gunicorn 显式指定工作目录

- systemd: 配置 `WorkingDirectory=...`
- gunicorn: 使用 `--chdir ...` 或保证运行目录为项目根

### 3) 把“包根目录注入”做成启动代码的一部分(下游入口)

如果你们有统一入口脚本(比如 Django 的 `wsgi.py`/`asgi.py` 或管理脚本),可以在入口处显式补齐 import roots,
但需要保持边界清晰(只把项目包根加进 `sys.path`,不要把任意 YAML 目录加进去)。

