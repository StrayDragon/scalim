# Design: demo_big_data_report YAML-first mainline (scenarios + suite split)

Date: 2026-03-20

This design captures the agreed direction for the repository’s **single mainline tutorial** (`notebooks/marimo/demo_big_data_report/`) to become **YAML DSL first** and scenario-driven, while moving public API coverage out into a dedicated examples suite.

OpenSpec SSOT for this plan:
- `openspec/changes/c16-demo-big-data-report-yaml-mainline/proposal.md`
- `openspec/changes/c16-demo-big-data-report-yaml-mainline/design.md`
- `openspec/changes/c16-demo-big-data-report-yaml-mainline/specs/**/spec.md`
- `openspec/changes/c16-demo-big-data-report-yaml-mainline/tasks.md`

## Background

Current issues:
- Mainline chapters mix in IR/Plan-level internals, which raises the learning and maintenance cost for engineering users who primarily want to author and ship YAML.
- YAML DSL features evolve (schema + validator), but the demo lacks an auditable “schema → examples → assertions” mapping, making drift likely.
- Public API `__all__` coverage chapters being embedded in the mainline tutorial damages narrative quality and increases churn.

## Goals

- Make `demo_big_data_report` a **YAML DSL mainline tutorial**: every chapter has a business background, a “request from a stakeholder”, a chosen approach, and a deterministic oracle.
- Build a first version of the **internet scenario library** under `by_yaml_dsl/`:
  - ecommerce (existing canonical SSOT, extended)
  - ads
  - support
- Add a **capability coverage matrix** (based on `demand.gen.json` + `workflow.gen.json`) mapping schema domains/keys to YAML fixtures and gate assertions.
- Split public API coverage (`__all__` + hooks/ob) into an independent suite, still executed by `just examples`.

## Non-Goals / Boundaries

- No new YAML DSL runtime/schema features; this change is an examples/tutorial governance refactor.
- No “data analyst pipeline” work; the target audience is engineering users integrating YAML into services.
- Keep canonical YAML paths stable (especially ecommerce SSOT files).

## Key Decisions

- **Two-suite structure**:
  - `demo_big_data_report`: YAML-first, scenario-driven tutorial + deterministic gate
  - `example_public_api_suite` (name TBD but explicit): `__all__` coverage + extension points, still in gate
- **Scenario organization**: due to imports V1 constraints, keep each scenario’s fragments in the same directory (e.g., `by_yaml_dsl/ads/`, `by_yaml_dsl/support/`).
- **Oracle strategy**: prefer pure-Python expected results; use small fixtures only when necessary (workflow artifacts, etc.).

## Validation

- YAML validation:
  - demand: `uv run scalim-cli yaml-dsl validate <file>`
  - workflow: `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <file>`
- Gate:
  - `just examples` runs both suites and all chapters pass deterministically
  - `just qa` passes (lint/tests + drift checks + OpenSpec checks)

