set dotenv-load := true

UV_OPTIONS := "--preview-features extra-build-dependencies"

# 统一在 just 子进程里固定到默认 PyPI,避免继承本地镜像环境后把 `uv.lock` 再次写脏。
export UV_DEFAULT_INDEX := "https://pypi.org/simple"
export UV_INDEX_URL := ""
export UV_EXTRA_INDEX_URL := ""
export PIP_INDEX_URL := ""
export PIP_EXTRA_INDEX_URL := ""

_default:
    just --list

# 构建文档站点: 预览
docs-serve *ARGS:
    just gen-docs
    uv {{ UV_OPTIONS }} run zensical serve -f docs/zensical.toml -a 0.0.0.0:8000 {{ ARGS }}

# 构建文档站点
docs-build: gen-docs
    uv {{ UV_OPTIONS }} run zensical build -f docs/zensical.toml

# 检查: frontend 公共流程 (install + lint + build)
_frontend-check DIR LABEL:
    #!/usr/bin/env bash
    set -euo pipefail
    dir="{{ DIR }}"
    label="{{ LABEL }}"
    if ! command -v pnpm >/dev/null 2>&1; then
        if [ -n "${CI:-}" ]; then
            echo "pnpm not found (required in CI for ${label})" >&2
            exit 1
        fi
        echo "pnpm not found; skipping ${label}" >&2
        exit 0
    fi
    pnpm -C "$dir" install --frozen-lockfile
    pnpm -C "$dir" audit --audit-level high --ignore-registry-errors
    pnpm -C "$dir" lint
    pnpm -C "$dir" build

# 检查: Scalim Viz 前端 (install + lint + build)
frontend-scalim-viz-check:
    just _frontend-check frontend/scalim-viz frontend-scalim-viz-check

# 检查: 所有 frontend (install + lint + build)
frontend-check:
    just frontend-scalim-viz-check

# 生成: YAML DSL 校验 schema
gen-yaml-dsl-schema:
    uv {{ UV_OPTIONS }} run python scripts/gen-yaml-dsl-schema.py

# 生成: 项目常量(从 `pyproject.toml` 派生;供 Python/前端统一引用)
gen-project-constants:
    uv {{ UV_OPTIONS }} run python scripts/gen-project-constants.py

# 检查: 项目常量生成物是否有 drift
project-constants-drift-check:
    uv {{ UV_OPTIONS }} run python scripts/gen-project-constants.py --check

# 检查: YAML DSL schema 生成物是否有 drift (含 canonical 文本形式)
schema-drift-check:
    uv {{ UV_OPTIONS }} run python scripts/gen-yaml-dsl-schema.py --check

# 检查: 受控生成物漂移 (约定: `*.gen.*` + injected blocks)
generated-artifacts-drift-check: project-constants-drift-check schema-drift-check validate-agent-skill validate-public-api-skill marimo-coverage-drift-check docs-drift-check

# 检查: 文档治理一致性(SSOT 入口/漂移源头)
doc-governance-check:
    uv {{ UV_OPTIONS }} run python scripts/check-doc-governance.py

# 检查: Markdown SSOT (legacy authoring surface)
md-ssot-check:
    uv {{ UV_OPTIONS }} run python scripts/check-md-ssot.py

# 检查: stdlib 同名模块冲突
stdlib-collisions-check:
    uv {{ UV_OPTIONS }} run python scripts/check-stdlib-module-collisions.py

# 依赖: 同步开发依赖
uv-sync-dev:
    #!/usr/bin/env bash
    set -euo pipefail
    env \
        -u UV_INDEX \
        -u UV_INDEX_URL \
        -u UV_EXTRA_INDEX_URL \
        -u PIP_INDEX_URL \
        -u PIP_EXTRA_INDEX_URL \
        UV_DEFAULT_INDEX="https://pypi.org/simple" \
        uv {{ UV_OPTIONS }} sync --locked


# 检查: `uv.lock` 是否与当前项目元数据一致(强制按默认 PyPI 校验,避免本地镜像环境掩盖 CI 漂移)
uv-lock-check:
    #!/usr/bin/env bash
    set -euo pipefail
    env \
        -u UV_INDEX \
        -u UV_INDEX_URL \
        -u UV_EXTRA_INDEX_URL \
        -u PIP_INDEX_URL \
        -u PIP_EXTRA_INDEX_URL \
        UV_DEFAULT_INDEX="https://pypi.org/simple" \
        uv {{ UV_OPTIONS }} lock --check

# 构建: wheel/sdist (发行物)
build-dist:
    uv {{ UV_OPTIONS }} build --wheel --sdist --no-create-gitignore --no-sources

# 检查: wheel/sdist 内容边界 (不应包含 tests/docs/notebooks/frontend/agentdev/artifacts)
dist-check: build-dist
    uv {{ UV_OPTIONS }} run python scripts/check-build-artifacts.py

# 生成: Viz 数据 (默认使用 demo_big_data_report 的 canonical YAML fixtures)
gen-viz-data PARAM="":
    uv {{ UV_OPTIONS }} run python scripts/gen-viz-data.py --mode events-only {{ PARAM }}
    # uv {{ UV_OPTIONS }} run python scripts/gen-viz-data.py --mode events+trace {{ PARAM }}

# 生成: workflow replay bundle (scalim-viz/workflow + child runs)
gen-viz-workflow-bundle PARAM="":
    uv {{ UV_OPTIONS }} run python scripts/gen-viz-workflow-bundle.py {{ PARAM }}

# 生成: demo_big_data_report 的 workflow demo baseline(含 bundle_manifest.json + report.xlsx/detail.csv/metrics.csv)
gen-viz-workflow-demo-big-data-report PARAM="":
    uv {{ UV_OPTIONS }} run python scripts/gen-viz-workflow-demo-big-data-report.py {{ PARAM }}

# 生成: Viz schedule plan (基于已生成的 viz_events.jsonl; 用于补齐/修复缺失的 viz_schedule_plan.json)
gen-viz-schedule-plan RUN_DIR="":
    #!/usr/bin/env bash
    set -euo pipefail

    if [ -n "{{ RUN_DIR }}" ]; then
        run_dirs=( "{{ RUN_DIR }}" )
    else
        run_dirs=()
        while IFS= read -r line; do
            run_dirs+=( "$line" )
        done < <(
            find .tmp/artifacts/scalim-viz/examples/demo_big_data_report -type f -name "viz_events.jsonl" -print \
                | sed 's#/viz_events.jsonl$##' \
                | sort -u
        )
    fi

    for dir in "${run_dirs[@]}"; do
        events_jsonl="${dir}/viz_events.jsonl"
        output_json="${dir}/viz_schedule_plan.json"

        if [ ! -f "$events_jsonl" ]; then
            echo "[warn] missing viz_events.jsonl:" "$events_jsonl" >&2
            continue
        fi
        if [ -f "$output_json" ]; then
            continue
        fi

        uv {{ UV_OPTIONS }} run python scripts/gen-viz-schedule-plan.py \
            --events-jsonl "$events_jsonl" \
            --output-json "$output_json"
    done

# 检查 Agent Skill 数据是否合法
validate-agent-skill:
    uv {{ UV_OPTIONS }} run python scripts/gen-agent-skill.py --validate

# 检查: scalim-public-api skill 受控产物漂移
validate-public-api-skill:
    uv {{ UV_OPTIONS }} run python scripts/gen-public-api-skill.py --validate

# 工具: 生成公共接口跳转辅助导入文件(用于编辑器/LSP 快速跳转; 生成物在 `.tmp/`)
gen-public-api-jump-imports:
    uv {{ UV_OPTIONS }} run python scripts/gen-public-api-jump-imports.py

# 工具: 生成 public API exports 审计视图(用于 review/对齐; 生成物在 `.tmp/`)
gen-public-api-exports-catalog:
    uv {{ UV_OPTIONS }} run python scripts/gen-public-api-exports-catalog.py

# 工具: `llmanspec/` 脱敏 (自动叠加本地 `sanitize_rules.local.yaml`; 默认强制 apply)
llmanspec-sanitize:
    uv {{ UV_OPTIONS }} run python scripts/sanitize.py --apply --root llmanspec

# 检查: `llmanspec/` 脱敏 (dry-run; 若存在命中则失败)
llmanspec-sanitize-check:
    #!/usr/bin/env bash
    set -euo pipefail
    set +e
    uv {{ UV_OPTIONS }} run python scripts/sanitize.py --check --root llmanspec
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
        echo ""
        echo "[error] llmanspec sanitize check failed; run: just llmanspec-sanitize" >&2
        exit "$rc"
    fi

# 检查: llmanspec 提案/规范的脱敏与结构校验 (自动叠加本地 `sanitize_rules.local.yaml`; 缺失时脚本仅在非 CI 告警)
#
# 注意:
# - 本 gate 默认严格检查：若发现命中，将自动 apply 脱敏并失败退出（避免敏感字面量继续停留在工作区/产物中）。
llmanspec-check:
    #!/usr/bin/env bash
    set -euo pipefail

    if command -v llman >/dev/null 2>&1; then
        llman sdd validate --all --strict --no-interactive
        exit 0
    fi

    ci_value="$(printf '%s' "${CI:-}" | tr '[:upper:]' '[:lower:]')"
    case "$ci_value" in
        ""|0|false|no|off)
            echo "[error] llman CLI not found; install it before running llmanspec-check." >&2
            exit 2
            ;;
        *)
            echo "[warn] llman CLI not found in CI; skipping llman sdd validate --all --strict --no-interactive." >&2
            exit 0
            ;;
    esac

# 工具: 统一主包/子包/前端版本 (默认 dry-run; 需要 YES 才执行)
bump-versions VERSION="" CONFIRM="":
    #!/usr/bin/env bash
    set -euo pipefail
    version="{{ VERSION }}"
    confirm="{{ CONFIRM }}"
    apply=""

    if [ "$confirm" = "YES" ] || [ "$confirm" = "CONFIRM=YES" ]; then
        apply="YES"
    elif [ -n "$confirm" ]; then
        echo "[warn] confirm token ignored (expected 'YES'):" "$confirm" >&2
    fi

    # 主包版本优先用 `uv version` 管理,避免忘记 re-lock.
    if [ -n "$version" ]; then
        if [ -n "$apply" ]; then
            uv {{ UV_OPTIONS }} version "$version"
            uv {{ UV_OPTIONS }} run python scripts/gen-project-constants.py
        else
            uv {{ UV_OPTIONS }} version --dry-run "$version"
        fi
    fi

    args=()
    if [ -n "$version" ]; then
        args+=( --version "$version" )
    fi
    if [ -n "$apply" ]; then
        args+=( --apply )
    fi
    uv {{ UV_OPTIONS }} run python scripts/bump-versions.py "${args[@]}"

    # bump 子包后需要更新 workspace lock,否则 `uv lock --check` 会失败.
    if [ -n "$apply" ]; then
        uv {{ UV_OPTIONS }} lock
    fi

# 工具: 将 src/scalim + README.md 镜像同步到目标 vendors 目录(默认 dry-run; 需要 YES 才执行)
sync-project-vendors PATH="" CONFIRM="":
    #!/usr/bin/env bash
    set -euo pipefail
    dest="{{ PATH }}"
    confirm="{{ CONFIRM }}"
    apply=""
    if [ -z "$dest" ]; then
        echo "[error] PATH is required (dest vendors root). Example:" >&2
        echo "  just sync-project-vendors /path/to/vendors/libs" >&2
        exit 2
    fi
    if [ "$confirm" = "YES" ] || [ "$confirm" = "CONFIRM=YES" ]; then
        apply="YES"
    elif [ -n "$confirm" ]; then
        echo "[warn] confirm token ignored (expected 'YES'):" "$confirm" >&2
    fi
    args=( --dest "$dest" )
    if [ -z "$apply" ]; then
        :
    else
        args+=( --apply )
    fi
    uv {{ UV_OPTIONS }} run python scripts/vendor-sync.py "${args[@]}"

# 生成: Agent Skill 数据
gen-agent-skill:
    uv {{ UV_OPTIONS }} run python scripts/gen-agent-skill.py

# 生成: scalim-public-api skill 受控参考产物
gen-public-api-skill:
    uv {{ UV_OPTIONS }} run python scripts/gen-public-api-skill.py

# 生成: notebooks/marimo 覆盖报告（generated）
gen-marimo-coverage:
    uv {{ UV_OPTIONS }} run python scripts/gen-marimo-coverage.py

# 检查: notebooks/marimo 覆盖报告是否有 drift
marimo-coverage-drift-check:
    uv {{ UV_OPTIONS }} run python scripts/gen-marimo-coverage.py --check

# 生成: 文档站点受控生成物(含 injected blocks)
gen-docs:
    uv {{ UV_OPTIONS }} run python scripts/gen-docs.py

# 检查: docs 生成物是否有 drift
docs-drift-check:
    uv {{ UV_OPTIONS }} run python scripts/gen-docs.py --check

# 生成: 所有需要生成的数据
gen: gen-project-constants gen-yaml-dsl-schema gen-agent-skill gen-public-api-skill gen-marimo-coverage gen-viz-data gen-viz-schedule-plan gen-docs

# 检查: 类型检查
type-check:
    uv {{ UV_OPTIONS }} run basedpyright src/scalim/ # --level error

# 检查: Docker 可用性
is-docker-available:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! docker version >/dev/null 2>&1; then
        echo "[error] docker unavailable; please start Docker and retry" >&2
        exit 1
    fi

# 检查: 核心链路更严格的类型边界(以 `pyproject.toml` 的 `tool.basedpyright.strict` 为准)
type-check-core-tight:
    uv {{ UV_OPTIONS }} run basedpyright $(uv {{ UV_OPTIONS }} run scripts/toml-get.py --file pyproject.toml --key tool.basedpyright.strict --format shell-words)

# 检查: packages/scalim-yaml-dsl-lsp 类型检查 (Python 3.10+)
type-check-packages-yaml-dsl-lsp:
    uv {{ UV_OPTIONS }} run basedpyright -p packages/scalim-yaml-dsl-lsp packages/scalim-yaml-dsl-lsp/src

# 检查: 格式化&Lint (只检查;不改文件)
lint: type-check type-check-core-tight
    uv {{ UV_OPTIONS }} run ruff format --check .
    uv {{ UV_OPTIONS }} run ruff check .

# 检查: 类型错误检查 / lint错误并修复
lintfix: type-check
    uv {{ UV_OPTIONS }} run ruff format .
    uv {{ UV_OPTIONS }} run ruff check --fix .

# 检查: 文档字符串/注释语言(中文为主;允许反引号包裹技术词)
py-doc-language-check:
    uv {{ UV_OPTIONS }} run python scripts/check-py-doc-language.py

# 检查: `src/scalim/` 运行时契约规则(`pyright` 顶层指令 + 严格顶层规则 + 类内 `if TYPE_CHECKING:` 条件方法)
top-level-pyright-pragmas-check:
    uv {{ UV_OPTIONS }} run python scripts/check-top-level-pyright-pragmas.py --strict-top-level

# 检查: `src/scalim/` 注释/文档字符串英文需用反引号包裹(更严格)
comments-cn-check:
    uv {{ UV_OPTIONS }} run python scripts/check-comments-cn.py

# 检查: 运行时输出文案语言(中文为主). 同时写入 `.tmp/artifacts/` 以便 CI 上传
py-output-language-check:
    uv {{ UV_OPTIONS }} run python scripts/check-py-output-language.py --report .tmp/artifacts/output-language.report.txt

# 检查: 运行单元测试
test:
    # Fast/local functional checks (bench excluded). Use for daily dev loops.
    uv {{ UV_OPTIONS }} run pytest tests/ -q

# 检查: 运行单元测试 (gate: xdist + coverage)
test-gate:
    uv {{ UV_OPTIONS }} run pytest tests/ -q -n auto --cov=scalim --cov-report=term-missing --cov-fail-under=100

# 检查: 生成 branch coverage 报告(不做阈值门禁;用于定位 missing branches)
test-gate-branch-report:
    uv {{ UV_OPTIONS }} run pytest tests/ -q -n auto --cov=scalim --cov-branch --cov-report=term-missing --cov-report=json:.tmp/coverage.json

# 检查: core 覆盖率 gate (statements + branches; core 由 allow-non-core-file 治理标记决定)
core-coverage-report:
    uv {{ UV_OPTIONS }} run python scripts/check-core-coverage.py --coverage-json .tmp/coverage.json --require-statements 100 --require-branches 100

# 检查: core 覆盖率 (statements + branches; core 由 allow-non-core-file 治理标记决定)
core-coverage-check:
    uv {{ UV_OPTIONS }} run python scripts/check-core-coverage.py --coverage-json .tmp/coverage.json --require-statements 100 --require-branches 100 --check

# 检查: 测试门禁覆盖率 (statements + branches; core 由 allow-non-core-file 治理标记决定)
test-gate-core-coverage:
    # 先执行 statements/line coverage gate(SSOT: --cov-fail-under=100),再执行 core branch gate.
    just test-gate
    just test-gate-branch-report
    just core-coverage-check

# 压力测试: 运行
bench *ARGS:
    # Performance baseline run only. Typical workflows:
    # - Save baseline: `just bench-baseline-save`
    # - Compare vs latest baseline: `just bench-compare`
    # - Gate regressions (default mean:10%): `just bench-compare-fail` or `just bench-compare-fail "mean:5%"`
    uv {{ UV_OPTIONS }} run pytest tests/bench -v -m bench --benchmark-only -n 0 --no-cov -o addopts="" {{ ARGS }}

# 压力测试: 保存基准
bench-baseline-save:
    uv {{ UV_OPTIONS }} run pytest tests/bench -v -m bench --benchmark-only -n 0 --no-cov --benchmark-save baseline -o addopts=""

# 压力测试: 对比基准
bench-compare:
    uv {{ UV_OPTIONS }} run pytest tests/bench -v -m bench --benchmark-only -n 0 --no-cov --benchmark-compare -o addopts=""

# 压力测试: 对比基准(失败阈值)
bench-compare-fail THRESH="mean:10%":
    # Default: mean:10%. Override: `just bench-compare-fail "mean:5%"`
    uv {{ UV_OPTIONS }} run pytest tests/bench -v -m bench --benchmark-only -n 0 --no-cov --benchmark-compare --benchmark-compare-fail {{ THRESH }} -o addopts=""

# 内存压力测试: 运行
bench-memray *ARGS:
    # Memray memory profiling (dev-only). Outputs to .benchmarks/memray/
    mkdir -p .benchmarks/memray
    uv {{ UV_OPTIONS }} run pytest tests/bench -v -m bench --benchmark-only -n 0 --no-cov -o addopts="" --memray --memray-bin-path .benchmarks/memray {{ ARGS }}

# 内存压力测试: 显示最耗内存的分配
bench-memray-most MOST:
    # Show top allocation sites while collecting memray output.
    mkdir -p .benchmarks/memray
    uv {{ UV_OPTIONS }} run pytest tests/bench -v -m bench --benchmark-only -n 0 --no-cov -o addopts="" --memray --memray-bin-path .benchmarks/memray --most-allocations {{ MOST }}

# Profiling: execution hotspots (dev-only)
profile-cpu SCALE="stress" TARGETS="relations" BATCH_SIZE="100":
    mkdir -p .tmp/artifacts/perf
    uv {{ UV_OPTIONS }} run py-spy record -o .tmp/artifacts/perf/ecommerce_{{ TARGETS }}_{{ SCALE }}_pyspy.svg -- \
        python scripts/profile-execution-hotspots.py --scale {{ SCALE }} --targets {{ TARGETS }} --batch-size {{ BATCH_SIZE }}

profile-cpu-top SCALE="stress" TARGETS="relations" BATCH_SIZE="100":
    uv {{ UV_OPTIONS }} run py-spy top -- \
        python scripts/profile-execution-hotspots.py --scale {{ SCALE }} --targets {{ TARGETS }} --batch-size {{ BATCH_SIZE }}

# 交互笔记: 打开笔记首页
notebook:
    uv {{ UV_OPTIONS }} run marimo edit notebooks/marimo/

# 运行示例: 大数据的示例
examples-big-data:
    uv {{ UV_OPTIONS }} run python notebooks/marimo/demo_big_data_report/demo_main.py

# 运行示例: 运行所有示例
examples:
    #!/usr/bin/env bash
    set -euo pipefail

    cd "{{ justfile_directory() }}"

    PYTHONPATH="{{ justfile_directory() }}${PYTHONPATH:+:$PYTHONPATH}" uv {{ UV_OPTIONS }} run python - <<'PY'
    import importlib
    import logging
    import multiprocessing as mp
    import os
    import sys
    from concurrent.futures import ProcessPoolExecutor
    from pathlib import Path
    from typing import Dict, List, Optional, Sequence

    from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
    from scalim_misc.examples.harness import exit_code, format_results, summarize_failures


    def _is_ci() -> bool:
        raw = str(os.environ.get("CI") or "").strip().lower()
        if not raw:
            return False
        return raw not in {"0", "false", "no"}


    def _parse_jobs() -> int:
        raw = str(os.environ.get("SCALIM_EXAMPLES_JOBS") or "").strip()
        if raw:
            jobs = int(raw)
            return max(1, jobs)
        return 1 if _is_ci() else 2


    def _parse_suites_whitelist() -> Optional[Sequence[str]]:
        raw = str(os.environ.get("SCALIM_EXAMPLES_SUITES") or "").strip()
        if not raw:
            return None
        parts: List[str] = []
        for item in raw.replace(";", ",").split(","):
            token = str(item).strip()
            if token:
                parts.append(token)
        if not parts:
            return None
        return sorted(set(parts))


    def _discover_suites(*, marimo_root: Path) -> List[str]:
        suites: List[str] = []
        for path in marimo_root.iterdir():
            if not path.is_dir():
                continue
            name = str(path.name)
            if name.startswith("demo_") or name.startswith("example_"):
                # 防御: 避免本地残留空目录/中间产物(无任何 `.py` 源码)被误识别为 suite,导致 gate 失败。
                # 真实 suite 至少应包含 1 个可 import 的 Python 模块(例如 `demo_main.py` 或 `chapters*/registry.py`)。
                if not any(path.rglob("*.py")):
                    continue
                suites.append(name)
        return sorted(suites)


    def _discover_chapter_groups(*, suite_dir: Path) -> List[str]:
        groups: List[str] = []
        for path in suite_dir.iterdir():
            if not path.is_dir():
                continue
            group_id = str(path.name)
            if not group_id.startswith("chapters"):
                continue
            if (path / "registry.py").is_file():
                groups.append(group_id)

        def _key(group_id: str) -> object:
            if group_id == "chapters_of_yaml_dsl":
                return (0, group_id)
            if group_id == "chapters_of_ir":
                return (1, group_id)
            return (2, group_id)

        return sorted(groups, key=_key)


    def _configure_logging() -> None:
        logging.basicConfig(level=logging.WARNING)
        noisy_loggers = [
            "scalim.execution.executor.runtime.runtime",
            "scalim.ob.presets.row_gap",
            "scalim.sinks.sink_csv",
        ]
        for name in noisy_loggers:
            logging.getLogger(name).setLevel(logging.ERROR if name == "scalim.sinks.sink_csv" else logging.WARNING)


    def _run_suite(suite_id: str) -> List[ExampleResult]:
        _configure_logging()

        repo_root = Path(".").resolve()
        suite_dir = repo_root / "notebooks" / "marimo" / str(suite_id)
        if not suite_dir.is_dir():
            return [
                ExampleResult(
                    example_id="suite/{}".format(suite_id),
                    passed=False,
                    kind=EXAMPLE_KIND_ORACLE,
                    summary="suite directory missing: {}".format(str(suite_dir)),
                    details={"suite_dir": str(suite_dir)},
                )
            ]

        groups = _discover_chapter_groups(suite_dir=suite_dir)
        if not groups:
            return [
                ExampleResult(
                    example_id="suite/{}".format(suite_id),
                    passed=False,
                    kind=EXAMPLE_KIND_ORACLE,
                    summary="no chapter groups found (expected `chapters*/registry.py`)",
                    details={"suite_dir": str(suite_dir)},
                )
            ]

        all_results: List[ExampleResult] = []
        for group_id in groups:
            registry_mod = "notebooks.marimo.{}.{}.registry".format(str(suite_id), str(group_id))
            try:
                reg = importlib.import_module(registry_mod)
                results = reg.run_all_chapters()
            except Exception as exc:  # noqa: BLE001
                all_results.append(
                    ExampleResult(
                        example_id="{}/{}".format(suite_id, group_id),
                        passed=False,
                        kind=EXAMPLE_KIND_ORACLE,
                        summary="{}: {}".format(type(exc).__name__, exc),
                        details={"registry_module": registry_mod, "exc_type": type(exc).__name__, "message": str(exc)},
                    )
                )
                continue
            all_results.extend(results)
        # 说明:
        # - 章节可能把局部函数/闭包等对象放入 `details`,导致多进程返回时无法 pickle。
        # - gate 输出仅依赖 example_id/passed/kind/summary,因此在 runner 边界主动丢弃 details。
        return [
            ExampleResult(
                example_id=str(r.example_id),
                passed=bool(r.passed),
                kind=str(r.kind or ""),
                summary=str(r.summary or ""),
                details=None,
            )
            for r in all_results
        ]


    def main() -> int:
        repo_root = Path(".").resolve()
        marimo_root = repo_root / "notebooks" / "marimo"
        suites = _discover_suites(marimo_root=marimo_root)
        if not suites:
            raise RuntimeError("no suites discovered under {}".format(str(marimo_root)))

        whitelist = _parse_suites_whitelist()
        if whitelist is not None:
            unknown = sorted(set(whitelist) - set(suites))
            if unknown:
                msg = "unknown suites in `SCALIM_EXAMPLES_SUITES`: {} (known: {})".format(", ".join(unknown), ", ".join(suites))
                raise ValueError(msg)
            suites = [s for s in suites if s in set(whitelist)]

        jobs = _parse_jobs()
        suite_results: Dict[str, List[ExampleResult]] = {}
        if jobs <= 1 or len(suites) <= 1:
            for suite_id in suites:
                suite_results[suite_id] = _run_suite(suite_id)
        else:
            try:
                ctx = mp.get_context("fork")
            except ValueError:
                ctx = mp.get_context()
            max_workers = min(int(jobs), len(suites))
            with ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as executor:
                futures = {executor.submit(_run_suite, suite_id): suite_id for suite_id in suites}
                for fut, suite_id in futures.items():
                    suite_results[suite_id] = fut.result()

        all_results: List[ExampleResult] = []
        for suite_id in suites:
            all_results.extend(suite_results.get(suite_id, []))

        for line in format_results(all_results):
            print(line)

        failures = summarize_failures(all_results)
        if failures:
            print("\n--- 失败详情 ---\n{}".format(failures), file=sys.stderr)
        if not failures:
            print("\n所有示例执行完成!")
        return exit_code(all_results)


    if __name__ == "__main__":
        raise SystemExit(main())
    PY

alias example := examples

# Prompt 评测: 确定性 core(不依赖密钥/网络/Node). 输出到 `.tmp/artifacts/prompt-eval/`
prompt-eval:
    uv {{ UV_OPTIONS }} run python scripts/prompt-eval.py

# Prompt 评测: CI/check 模式(确定性 core + 受控输出)
prompt-eval-check:
    uv {{ UV_OPTIONS }} run python scripts/prompt-eval.py --check

# Prompt 评测: 可选模型层(独立入口; 当前仅占位)
prompt-eval-llm:
    uv {{ UV_OPTIONS }} run python scripts/prompt-eval.py --llm

# Prompt 评测: 可选模型层(在仓库外的临时目录; 避免 uv/.venv 冲突)
prompt-eval-llm-tmp OUTPUT_DIR="/tmp/scalim-prompt-eval":
    python scripts/prompt-eval.py --llm --output-dir "{{ OUTPUT_DIR }}"

# Prompt 评测: 可选 coding-agent 套件(promptfoo + agent; 昂贵)
prompt-eval-agent:
    uv {{ UV_OPTIONS }} run python scripts/prompt-eval.py --llm-agent

# Prompt 评测: coding-agent 套件(仓库外临时目录; 避免 uv/.venv 冲突)
prompt-eval-agent-tmp OUTPUT_DIR="/tmp/scalim-prompt-eval-agent":
    python scripts/prompt-eval.py --llm-agent --output-dir "{{ OUTPUT_DIR }}"

# 报告: cast 使用基线
report-cast-usage:
    uv {{ UV_OPTIONS }} run python scripts/check-cast-usage.py

# 检查: cast 使用必须显式 allow
check-cast-usage:
    uv {{ UV_OPTIONS }} run python scripts/check-cast-usage.py --check

# 报告: pragma no cover 基线
report-no-cover:
    uv {{ UV_OPTIONS }} run python scripts/check-no-cover.py

# 检查: pragma no cover 必须显式 allow
check-no-cover:
    uv {{ UV_OPTIONS }} run python scripts/check-no-cover.py --check

# 检查: `# pragma: no branch` 使用必须显式 allow
check-no-branch:
    uv {{ UV_OPTIONS }} run python scripts/check-no-branch.py --check

# 报告: dynattr 使用基线
report-dynattr:
    uv {{ UV_OPTIONS }} run python scripts/check-dynattr.py

# 检查: dynattr 使用必须显式 allow
check-dynattr:
    uv {{ UV_OPTIONS }} run python scripts/check-dynattr.py --check

# 报告: hotspot module 体量基线
report-module-size:
    uv {{ UV_OPTIONS }} run python scripts/check-module-size.py

# 检查: hotspot module 体量护栏(避免继续增长)
check-module-size:
    uv {{ UV_OPTIONS }} run python scripts/check-module-size.py --check

# 报告: core event dispatch map 完整性基线
report-dispatch-map-completeness:
    uv {{ UV_OPTIONS }} run python scripts/check-dispatch-map-completeness.py

# 检查: core event dispatch map 完整性(新增事件需显式加入/忽略)
check-dispatch-map-completeness:
    uv {{ UV_OPTIONS }} run python scripts/check-dispatch-map-completeness.py --check

# 报告: print(...) 使用基线
report-print-usage:
    uv {{ UV_OPTIONS }} run python scripts/check-no-print.py

# 检查: runtime 禁止 print(...)
check-no-print:
    uv {{ UV_OPTIONS }} run python scripts/check-no-print.py --check

# 检查: tests/ 禁止 time.sleep 轮询 (allowlist 除外)
check-no-test-sleep:
    uv {{ UV_OPTIONS }} run python scripts/check-no-test-sleep.py --check

# 报告: noqa C901 使用基线
report-noqa-c901:
    uv {{ UV_OPTIONS }} run python scripts/check-noqa-c901.py

# 检查: `# noqa: C901` 必须显式 allow 且携带 plan
check-noqa-c901:
    uv {{ UV_OPTIONS }} run python scripts/check-noqa-c901.py --check

# 检查: public API surface governance (`__all__` 约束 + 内部模块封堵)
check-api-surface-governance:
    uv {{ UV_OPTIONS }} run python scripts/check-api-surface-governance.py --check

# 检查: Tier 1 curated entrypoints 一致性(marker 语法 + 去重 + 模块存在 + 字面量 `__all__`)
check-public-api-curated-entrypoints:
    uv {{ UV_OPTIONS }} run python scripts/check-public-api-curated-entrypoints.py --check

# 检查: Tier1 curated entrypoints 与 examples/pytest public_api suite 覆盖漂移
check-public-api-suite-coverage:
    uv {{ UV_OPTIONS }} run python scripts/check-public-api-suite-coverage.py --check

# 检查: export API(`__all__`) 必须使用 tuple 字面量
check-export-api-must-tuple:
    uv {{ UV_OPTIONS }} run scripts/check-export-api-must-tuple.py --check

# 检查: user-facing materials 不得引用内部/不安全导入路径
check-user-material-import-boundaries:
    uv {{ UV_OPTIONS }} run python scripts/check-user-material-import-boundaries.py --check

# 检查: 主包导入图无环 + 禁止函数内导入
check-import-graph:
    uv {{ UV_OPTIONS }} run python scripts/check-import-graph.py --check

# 检查: workflow layering gate (workflow 不得依赖 dsl; yaml_dsl/runtime 不得包含 workflow_*.py)
check-workflow-layering:
    uv {{ UV_OPTIONS }} run python scripts/check-workflow-layering.py --check

# 检查: tests domain suites gate (目录结构 + tests.* 字符串引用边界)
check-tests-domain-suites:
    uv {{ UV_OPTIONS }} run python scripts/check-tests-domain-suites.py --check

# 检查: monkeypatch policy gate (禁止 patch private name / patch global import)
check-monkeypatch-policy:
    uv {{ UV_OPTIONS }} run python scripts/check-monkeypatch-policy.py --check

# 报告: `object` 类型标注基线
report-object-type:
    uv {{ UV_OPTIONS }} run python scripts/check-object-type.py

# 检查: `object` 类型标注必须显式 allow (scripts/vendor 白名单除外)
check-object-type:
    uv {{ UV_OPTIONS }} run python scripts/check-object-type.py --check

# QA: 仅py轻量的检查(不含 tests gate; 便于组合复用)
quick-check-only-py-no-test-gate: uv-lock-check lint type-check-packages-yaml-dsl-lsp check-cast-usage check-no-cover check-no-branch check-dynattr check-module-size check-dispatch-map-completeness check-no-print check-no-test-sleep check-noqa-c901 check-api-surface-governance check-public-api-curated-entrypoints check-public-api-suite-coverage check-export-api-must-tuple check-user-material-import-boundaries check-import-graph check-workflow-layering check-tests-domain-suites check-monkeypatch-policy py-doc-language-check top-level-pyright-pragmas-check comments-cn-check py-output-language-check generated-artifacts-drift-check doc-governance-check md-ssot-check stdlib-collisions-check llmanspec-check

# QA: 仅py轻量的检查
quick-check-only-py: quick-check-only-py-no-test-gate test-gate

alias quick-qa-only-py := quick-check-only-py

# QA: 所有轻量的检查
quick-check: quick-check-only-py

alias quick-qa := quick-check

# QA: 仅py完整的检查(不包含 frontend; 作为 qa 的可组合基础)
check-only-py: quick-check-only-py-no-test-gate test-gate-core-coverage py36-compat-check py36-typingext-check

# QA: 所有完整的检查(最全面入口; MUST 覆盖全部质量门禁)
check: check-only-py frontend-check examples

alias qa := check

# 检查: `Python 3.6` 语法兼容性 (仅 `src/scalim/`)
py36-compat-check:
    #!/usr/bin/env bash
    set -euo pipefail

    if docker version >/dev/null 2>&1; then
        docker run --rm -e CI -v "{{ justfile_directory() }}:/repo" -w /repo python:3.6 python -m compileall -q src/scalim
        exit 0
    fi

    echo "[error] docker unavailable; py36-compat-check requires docker. Please install/start docker and retry." >&2
    exit 1

# 检查: `Python 3.6` + `typing-extensions==4.1.1` 隔离环境兼容性
py36-typingext-check:
    #!/usr/bin/env bash
    set -euo pipefail

    just gen-public-api-jump-imports

    if docker version >/dev/null 2>&1; then
        docker run --rm -e CI -v "{{ justfile_directory() }}:/repo" -w /repo python:3.6 bash /repo/scripts/check-py36-typingext-docker.sh
        exit 0
    fi

    echo "[error] docker unavailable; py36-typingext-check requires docker. Please install/start docker and retry." >&2
    exit 1

# 清理缓存/产物 (默认 dry-run; 需要 YES 才执行)
clean-cache CONFIRM="":
    #!/usr/bin/env bash
    set -euo pipefail
    shopt -s nullglob

    confirm="{{ CONFIRM }}"
    root="{{ justfile_directory() }}"

    cd "$root"

    mode="dry-run"
    if [ "$confirm" = "YES" ]; then
        mode="execute"
    elif [ -n "$confirm" ]; then
        echo "[warn] confirm token ignored (expected 'YES'):" "$confirm" >&2
    fi

    targets=()

    add_if_exists() {
        local p="$1"
        if [ -e "$p" ]; then
            targets+=( "$p" )
        fi
    }

    add_find_dirs() {
        local find_root="$1"
        local name="$2"

        if [ ! -d "$find_root" ]; then
            return 0
        fi

        while IFS= read -r d; do
            targets+=( "$d" )
        done < <(
            find "$find_root" \
                -type d \( -name .git -o -name .venv -o -name node_modules \) -prune -false \
                -o -type d -name "$name" -prune -print
        )
    }

    # light
    add_if_exists .ruff_cache
    add_if_exists .pytest_cache
    add_if_exists .mypy_cache
    add_if_exists .pytype
    add_if_exists .pyre
    add_if_exists .hypothesis
    add_if_exists .cache
    add_if_exists .benchmarks/memray
    add_if_exists .uv-cache

    add_if_exists .coverage
    for f in .coverage.*; do
        add_if_exists "$f"
    done
    add_if_exists coverage.xml
    add_if_exists htmlcov

    add_if_exists build
    add_if_exists dist
    add_if_exists site

    add_find_dirs . __pycache__
    # add_if_exists .tmp
    # add_find_dirs . .tmp

    while IFS= read -r d; do
        targets+=( "$d" )
    done < <(find . -maxdepth 3 -type d -name "*.egg-info" -prune -print)

    # Normalize + dedupe + sort
    if [ "${#targets[@]}" -eq 0 ]; then
        echo "MODE=$mode ROOT=$root"
        echo "[ok] nothing to clean"
        exit 0
    fi

    mapfile -t targets < <(
        printf "%s\n" "${targets[@]}" \
            | sed 's#^\./##' \
            | awk 'NF' \
            | sort -u
    )

    echo "MODE=$mode ROOT=$root"
    printf "%s\n" "${targets[@]}"

    if [ "$mode" = "dry-run" ]; then
        echo ""
        echo "Dry-run only."
        echo "To execute:"
        echo "  just clean-cache YES"
        exit 0
    fi

    git_tracked() {
        local p="$1"
        if ! command -v git >/dev/null 2>&1; then
            return 1
        fi
        if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
            return 1
        fi
        git ls-files --error-unmatch -- "$p" >/dev/null 2>&1
    }

    safe_rm_rf() {
        local p="$1"

        case "$p" in
            ""|"."|"./")
                echo "[skip unsafe] empty or root path" >&2
                return 0
                ;;
            /*)
                echo "[skip unsafe] absolute path:" "$p" >&2
                return 0
                ;;
            ../*|./../*|*/../*|*/..|*/../)
                echo "[skip unsafe] path traversal:" "$p" >&2
                return 0
                ;;
        esac

        if git_tracked "$p"; then
            echo "[skip tracked]" "$p" >&2
            return 0
        fi

        rm -rf -- "$p"
        echo "[rm]" "$p" >&2
    }

    for p in "${targets[@]}"; do
        if [ -e "$p" ]; then
            safe_rm_rf "$p"
        fi
    done
