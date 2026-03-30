# Design: Public API import guide + structure evaluation

Date: 2026-03-28

This design captures the agreed direction to add a single, user-facing documentation page that answers:

1) Which `scalim.*` modules are the recommended public import entrypoints?
2) What is the current public API surface shape, and how healthy is it?
3) What are the governance gates and the high-level optimization directions (without landing breaking refactors)?

## Background

The repo has explicit public API governance via:

- module `__all__` governance rules (internal modules must not export): `scripts/check-api-surface-governance.py`
- user-facing materials import boundaries (docs/notebooks/skills): `scripts/check-user-material-import-boundaries.py`
- interactive + headless coverage suite: `notebooks/marimo/example_public_api_suite/`

However, docs lacked a single “import guide” page, and advanced modules (`events`/`sinks`) have a relatively large, flat export surface that increases long-term governance cost.

## Goals

- Add one page under “Getting Started” that:
  - lists Tier 1 curated public modules and what they’re for
  - lists common Tier 2 public modules with explicit stability caveats
  - documents the governance / validation commands contributors should run
  - provides a lightweight structure evaluation + score, with explicit costs and options
- Keep content aligned with the runtime gates; do not mention internal YAML DSL module paths.

## Non-Goals / Boundaries

- No API refactor / re-export restructuring in this change.
- No compatibility shims / deprecation layers; any future API surface shrink is treated as an explicit breaking change and should be managed via OpenSpec + versioning.
- Do not edit `.gen.*` docs pages or injected blocks in docs.

## Placement Decisions

User-selected choices:

- **Nav location**: under docs navigation “从这里开始” (Getting Started).
- **Content packaging**: a **single page** that includes “import guide + evaluation/score + costs/options”.

## Content Outline

The page should include:

1. Definition of public API + SSOT pointers (tests/scripts/notebooks)
2. Tier 1 curated modules: recommended imports + use-cases
3. Tier 2 modules: explicit caveats + guidance for pinning/self-regression
4. Governance: `__all__` meaning + scripts/tests + gate commands
5. Structure evaluation snapshot + score (with current `__all__` sizes)
6. Brainstorming options for future evolution (documentation-only / subgroup modules / shrink `__all__`)

## Validation

- `just qa`
- `just openspec-check`
