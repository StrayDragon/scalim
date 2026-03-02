set dotenv-load

_default:
    just --list

# 安装/更新开发环境
sync:
    uv sync --dev

# 类型检查
type-check:
    uv run basedpyright --level error src/scalim

# 格式化 + Lint(tests 在 ruff 配置中被忽略,但这里仍保留一致性)
fmt:
    uv run ruff format .

lint:
    uv run ruff check src/scalim tests

lang-check:
    uv run python scripts/check_py_doc_language.py

lintfix: type-check
    uv run ruff format .
    uv run ruff check --fix src/scalim tests

# 运行单元测试(覆盖率与 xdist 由 pyproject.toml 控制)
test:
    uv run pytest

# 轻量 QA(不跑 perf/bench,不生成 DSL 产物)
quick-check: lintfix test

alias quick-qa := quick-check
alias qa := quick-check

# 运行 marimo 示例脚本(非 DSL)
examples-big-data:
    #!/usr/bin/env bash
    set -euo pipefail

    out="$(mktemp -t scalim-demo-tutor-XXXXXX.html)"
    uv run marimo export html notebooks/marimo/examples/demo_big_data_report/demo_tutor.py -o "$out" --no-include-code
    echo "Exported: $out"

examples: examples-big-data

notebook:
    uv run marimo edit notebooks/marimo/examples/demo_big_data_report/demo_tutor.py

# 构建文档站点(MkDocs)+ 导出 marimo notebooks 到 docs/
docs-export-notebooks:
    uv run python scripts/export_marimo_to_docs.py --clean

docs-build: docs-export-notebooks
    NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict

docs-serve: docs-export-notebooks
    NO_MKDOCS_2_WARNING=1 uv run mkdocs serve -a 127.0.0.1:8000
