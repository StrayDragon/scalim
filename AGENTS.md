# Repository Guidelines

## Project Structure & Module Organization
- `src/scalim/` is the library package. Key areas include:
  - `dsl/by_yaml/` (YAML DSL): `config_parsing/` (parser/validator/security/index), `schema_dsl/` (schema + config models), `runtime/` (run_yaml + output plan)
  - `spec/` (IR types and relation DSL)
  - `planning/` (plan builder, operators, metadata, stages)
  - `execution/` (pipeline + executor split)
  - `sinks/` (outputs) and `sinks/sink_pandas.py` (optional pandas)
  - `events/` (event envelope + catalog)
  - `ob/` (observer manager + presets)
  - `hooks/` (flow customization hooks)
  - `utils/`, `vendor/`, `typedefs.py`
- `packages/scalim-benchlib/` provides benchmark helpers.
- `tests/` contains the pytest suite; `tests/bench/` is benchmark-only.
- `scripts/` holds developer utilities (schema generation, agent skill export). Script filenames under `scripts/` use kebab-case with `-` separators.
- `notebooks/` contains marimo demo scripts.
- `openspec/` and `ARCH.md` capture architecture and change proposals.

## Build, Test, and Development Commands
- `just --list`: discover all latest available tasks.
- `just qa`: lint+tests + 主要脚本检查(语言/漂移/stdlib 冲突等).
- `just check`: 在 `just qa` 基础上额外跑 frontend/examples/bench/memray(更慢).
- `just gen`: generate all artifacts (viz data, agent skill, etc.).

## Coding Style & Naming Conventions
- Python only; 4-space indent; line length 140; double quotes (ruff formatter).
- Use ruff as the source of truth for formatting and linting.
- Keep code compatible with Python 3.6 runtime even though dev uses 3.10+ (avoid 3.7+ only syntax).
- Import rule: inside `scalim/` prefer relative imports; avoid `import scalim` or `from scalim...`. Tests/scripts can import `scalim` directly.
- Scripts in `scripts/` should use `-`-separated filenames (for example, `gen-agent-skill.py`).
- Tests: file names `tests/test_*.py`, functions `test_*`.

## Runtime Contract Rules
- Do not define conditional methods or ellipsis stubs inside real runtime classes under `if TYPE_CHECKING:` to satisfy the type checker. This includes mixins, managers, handlers, and other production classes.
- `if TYPE_CHECKING:` is only for type-only imports, aliases, and other non-runtime declarations; it must not be used to fake class interfaces.
- When one mixin/class depends on methods provided by another mixin/class, express that dependency as an explicit runtime contract. Prefer `ABC` + `@abstractmethod` because it is Python 3.6 compatible and keeps MRO requirements visible.
- Do not use lazy local imports or other ad-hoc tricks as a substitute for proper runtime contracts unless the user explicitly asks for a compatibility workaround.

## Python Version & Packaging (Intentional Mismatch)
- Runtime compatibility target: `scalim/` must remain compatible with **Python 3.6** (and 3.10+ for dev/tests).
- Packaging metadata in `pyproject.toml` sets `requires-python = ">=3.10"` intentionally:
  - dev tooling uses `uv` and modern dependency constraints (uv does not support Python 3.6 environments),
  - we still keep runtime code 3.6-compatible for production/server deployments.
- Do not "fix" this by changing `requires-python` without an explicit packaging/distribution decision (it will affect how/where the package can be installed).

## typing_extensions Compatibility
Production servers may use older `typing_extensions` versions (e.g., 4.1.1 with Python 3.6). Use `scalim/vendor/compact/typing_extensionsx.py` for compatibility shims:
- `override`: decorator fallback for older versions.
- `Self`: type alias fallback (runtime uses `TypeVar("Self")`, type-checking uses real `Self` if available).

When adding new typing_extensions features, add a compat shim in `typing_extensionsx.py` and import from there instead of `typing_extensions` directly.

## Testing Guidelines
- Framework: pytest + xdist. Coverage is enabled by default in config.
- Mark slow tests with `@pytest.mark.slow` and run fast suite with `pytest -m "not slow"`.
- Benchmarks use `@pytest.mark.bench` and run only via `just bench` / `just bench-memray`.
- Add regression tests near the affected module and update fixtures under `tests/fixtures` when needed.

## Spec Hygiene
- After spec edits, run `just openspec-check`.
- `just openspec-check` runs both `scripts/sanitize.py --check --root openspec` and `openspec validate --all --strict --no-interactive`.
- `scripts/sanitize.py` must apply both `openspec/sanitize_rules.yaml` and `openspec/sanitize_rules.local.yaml` when the local file exists.
- If `openspec/sanitize_rules.local.yaml` is missing, the sanitize step will warn. Treat that warning as a prompt to confirm whether extra organization/private literals need additional local masking rules before publishing or sharing OpenSpec artifacts.

## Commit & Pull Request Guidelines
- Commit messages typically use a short type prefix: `fix:`, `tests:`, `doc:`, `scalim:`, or simple `sync`/`tmp`. Follow this style and keep summaries concise.
- PRs should include purpose, key changes, test commands run, and any schema changes (for example, mention `just gen-yaml-dsl-schema`). Add tests for behavior changes and update docs (`README.md`, `ARCH.md`) when relevant.

## Configuration & Safety Tips
- When editing YAML DSL rules, regenerate and validate the schema: `just gen-yaml-dsl-schema` and `uv run scalim-cli yaml-dsl validate <file.yaml>`.
- CLI install (recommended): `uv tool install scalim[cli]` (fallback: `pip install --user scalim[cli]`).
- Some sinks require optional dependencies (for example, Excel output needs `openpyxl`); call out new optional deps in docs/tests.
- Do not remove `# region SCALIM-SKILL:<tag>` / `# endregion` markers; they are used for automated skill example extraction.

## Privacy & Desensitization
- When assessing whether external repos/paths need coordinated updates, you may read `.tmp/known-outer-paths-using-this-package.txt`.
- For desensitization, do not quote, enumerate, or summarize the contents of `.tmp/known-outer-paths-using-this-package.txt` in chat output, docs, or spec artifacts; only reference the file path.
