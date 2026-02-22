set dotenv-load

_default:
    just --list

# Install / update the dev environment
sync:
    uv sync --dev

# Type checking
type-check:
    uv run basedpyright --level error src/scalim

# Formatting + lint (tests are ruff-ignored by config, but included for consistency)
fmt:
    uv run ruff format .

lint:
    uv run ruff check src/scalim tests

lintfix: type-check
    uv run ruff format .
    uv run ruff check --fix src/scalim tests

# Run unit tests (pyproject.toml controls coverage + xdist settings)
test:
    uv run pytest

# Lightweight QA (no perf/bench, no DSL artifacts)
quick-check: lintfix test

alias quick-qa := quick-check
alias qa := quick-check

# Run marimo example scripts (non-DSL)
examples-big-data:
    #!/usr/bin/env bash
    set -euo pipefail

    out="$(mktemp -t scalim-demo-tutor-XXXXXX.html)"
    uv run marimo export html notebooks/marimo/examples/demo_big_data_report/demo_tutor.py -o "$out" --no-include-code
    echo "Exported: $out"

examples: examples-big-data

notebook:
    uv run marimo edit notebooks/marimo/examples/demo_big_data_report/demo_tutor.py

# Build docs site (MkDocs) + export marimo notebooks into docs/
docs-export-notebooks:
    uv run python scripts/export_marimo_to_docs.py --clean

docs-build: docs-export-notebooks
    NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict

docs-serve: docs-export-notebooks
    NO_MKDOCS_2_WARNING=1 uv run mkdocs serve -a 127.0.0.1:8000
