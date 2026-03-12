# Repository Guidelines

## Quick Commands (SSOT Entry Points)
- `just --list`: discover tasks.
- `just qa`: repo quality gates (lint/tests + drift checks + OpenSpec checks, etc.).
- `just gen-docs`: refresh docs-site generated pages and injected blocks.
- `just openspec-check`: sanitize + validate OpenSpec artifacts.

## Hard Rules (SSOT)
- **Python runtime boundary**: code under `src/scalim/` MUST remain compatible with Python 3.6 (dev tooling is typically Python 3.10+; see `pyproject.toml`).
- **Formatting**: Python-only; 4-space indent; line length 140; double quotes (ruff formatter). Use ruff as the source of truth for formatting and linting.
- **Imports**: inside `src/scalim/` prefer relative imports; avoid `import scalim` / `from scalim...` (tests/scripts/notebooks may import `scalim` directly).
- **Runtime contracts**:
  - `if TYPE_CHECKING:` is only for type-only imports/aliases; MUST NOT be used to fake class interfaces (conditional methods / ellipsis stubs).
  - When one mixin/class depends on methods provided by another mixin/class, express that dependency as an explicit runtime contract (prefer `ABC` + `@abstractmethod`, Python 3.6 compatible).
- **typing_extensions**: keep runtime compatible with older `typing_extensions`; use `src/scalim/vendor/compact/typing_extensionsx.py` shims when needed.
- **Doc governance**:
  - Any file containing `.gen.` is generated; do not edit by hand. Edit SSOT and run `just gen-docs` (or the referenced generator).
  - Any `<!-- BEGIN AUTOGEN:<id> -->` / `<!-- END AUTOGEN:<id> -->` block is injected; do not edit inside the block. Edit SSOT and run `just gen-docs`.
- **Skills extraction markers**: do not remove `# region SCALIM-SKILL:<tag>` / `# endregion` markers (used for automated skill example extraction).
- **Privacy**: do not quote, enumerate, or summarize the contents of `.tmp/known-outer-paths-using-this-package.txt`; only reference the file path.

## Pointers (keep this file small)
- Project/code reading map: `docs/doc/getting-started/reading-guide.md`
- Docs governance workflow: `docs/doc/dev/doc-governance.md`
- Docs site config + content root: `docs/zensical.toml`, `docs/doc/`
- OpenSpec specs: `openspec/specs/` and `docs/doc/specs/index.md`
- Architecture overview: `ARCH.md` and `docs/doc/architecture/arch.md`
