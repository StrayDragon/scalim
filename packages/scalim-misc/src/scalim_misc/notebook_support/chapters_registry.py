from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from pathlib import Path
from re import Pattern
from typing import TYPE_CHECKING

from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from typing import Any

_RUN_RESOLVER_STANDARD = "standard"
_RUN_RESOLVER_ALLOW_UNIQUE = "allow_unique_run"
_CHAPTER_RESULT_KEY = "chapter_result"
# `app.run()` -> `(outputs, namespace)`.
_APP_RUN_ITEMS = 2


def _marimo_app_projection(mod: object) -> Callable[[], Any] | None:
    """Build a runner from the module's marimo ``app`` (cells-native fallback).

    marimo serializes a notebook as ``app = marimo.App(...)`` + ``@app.cell`` cells, and
    re-saving (editor or `marimo upgrade`) keeps **only** that shape. So the app itself is
    the execution SSOT: `app.run()` executes every cell in dependency order and returns
    `(outputs, namespace)`, where the namespace is a read-only view of the cell-defined
    names; the last teaching cell defines ``chapter_result``.

    Returns ``None`` when the module exposes no runnable marimo ``app``, so callers can keep
    the original "missing callable" diagnostics.
    """
    app = getattr(mod, "app", None)
    app_run = getattr(app, "run", None)
    if not callable(app_run):
        return None
    module_name = str(getattr(mod, "__name__", mod))

    def _run() -> Any:
        executed = app_run()
        # marimo returns `(outputs, namespace)`; stay tolerant of a bare namespace/mapping.
        namespace: object = executed[1] if isinstance(executed, tuple) and len(executed) == _APP_RUN_ITEMS else executed
        lookup = getattr(namespace, "get", None)
        if not callable(lookup):
            msg = f"marimo `app.run()` gave no definitions namespace in chapter module: {module_name}"
            raise TypeError(msg)
        chapter_result = lookup(_CHAPTER_RESULT_KEY)
        if not isinstance(chapter_result, dict):
            msg = f"marimo cells in chapter module {module_name} did not define `{_CHAPTER_RESULT_KEY}` dict"
            raise TypeError(msg)
        return chapter_result

    return _run


@dataclass(frozen=True)
class _Case:
    chapter_id: str
    run: Callable[[], ExampleResult]


class ChapterRegistry:
    def __init__(
        self,
        *,
        registry_file: str | Path,
        module_name_prefix: str,
        example_id_prefix: str,
        chapter_file_pattern: str | Pattern[str],
        chapter_id_group: int | str = 1,
        run_resolver: str = _RUN_RESOLVER_STANDARD,
    ) -> None:
        self._registry_file = Path(registry_file).resolve()
        self._module_name_prefix = str(module_name_prefix)
        self._example_id_prefix = str(example_id_prefix)
        self._chapter_file_re = re.compile(chapter_file_pattern) if isinstance(chapter_file_pattern, str) else chapter_file_pattern
        self._chapter_id_group = chapter_id_group
        self._run_resolver = str(run_resolver)
        self._chapters = self._discover_chapter_modules()
        self._chapter_modules_by_id = dict(self._chapters)
        self._all_chapter_ids = [chapter_id for chapter_id, _module_name in self._chapters]

    def _discover_chapter_modules(self) -> list[tuple[str, str]]:
        chapters_dir = self._registry_file.parent
        found: list[tuple[str, str, str]] = []
        for path in chapters_dir.iterdir():
            if not path.is_file() or path.name == self._registry_file.name:
                continue
            match = self._chapter_file_re.match(path.name)
            if not match:
                continue
            chapter_id = str(match.group(self._chapter_id_group))
            module_name = f"{self._module_name_prefix}.{path.stem}"
            found.append((path.name, chapter_id, module_name))
        found.sort(key=lambda item: item[0])

        chapters: list[tuple[str, str]] = []
        seen = set()
        for _filename, chapter_id, module_name in found:
            if chapter_id in seen:
                msg = f"Duplicate chapter_id discovered: {chapter_id}"
                raise ValueError(msg)
            seen.add(chapter_id)
            chapters.append((chapter_id, module_name))
        return chapters

    def all_chapter_ids(self) -> list[str]:
        return list(self._all_chapter_ids)

    def iter_chapters(self) -> Iterable[str]:
        return tuple(self._all_chapter_ids)

    def get_chapter_module_name(self, chapter_id: str) -> str:
        if chapter_id not in self._chapter_modules_by_id:
            msg = f"unknown chapter_id: {chapter_id}"
            raise KeyError(msg)
        return self._chapter_modules_by_id[chapter_id]

    def _resolve_run(self, mod: object, chapter_id: str) -> Callable[[], ExampleResult]:
        """Resolve the chapter's executable entry, in this priority.

        1. ``run_{chapter_id}()`` — per-chapter named adapter (legacy).
        2. ``run_chapter()`` — thin module-level adapter (marimo re-save tolerant).
        3. ``run()`` / (allow_unique) a single ``run_*()`` — 兼容旧写法.
        4. marimo ``app.run()`` projection -> ``chapter_result`` (cells-native SSOT).
        """
        run_fn_name = f"run_{chapter_id}"
        run = getattr(mod, run_fn_name, None)
        if callable(run):
            return run

        run = getattr(mod, "run_chapter", None)
        if callable(run):
            return run

        run = getattr(mod, "run", None)
        if callable(run):
            return run

        unique_hint = ""
        if self._run_resolver == _RUN_RESOLVER_ALLOW_UNIQUE:
            candidates = []
            for name in dir(mod):
                if not name.startswith("run_") or name == "run_chapter":
                    continue
                fn = getattr(mod, name, None)
                if callable(fn):
                    candidates.append(fn)
            if len(candidates) == 1:
                return candidates[0]
            unique_hint = "/single `run_*()`"

        projected = _marimo_app_projection(mod)
        if projected is not None:
            return projected

        msg = "missing callable `{}` (or `run_chapter()`/`run()`{}) in chapter module: {}".format(
            run_fn_name, unique_hint, getattr(mod, "__name__", mod)
        )
        raise AttributeError(msg)

    def _load_case(self, chapter_id: str) -> _Case:
        mod = importlib.import_module(self.get_chapter_module_name(chapter_id))
        return _Case(chapter_id=chapter_id, run=self._resolve_run(mod, chapter_id))

    def _safe_run(self, case: _Case) -> ExampleResult:
        example_id = f"{self._example_id_prefix}/{case.chapter_id}"
        try:
            result = case.run()
        except Exception as exc:  # noqa: BLE001
            return ExampleResult(
                example_id=example_id,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary=f"{type(exc).__name__}: {exc}",
                details={"exc_type": type(exc).__name__, "message": str(exc)},
            )
        # Dict result support: cells-native notebooks return chapter_result dict
        if isinstance(result, dict):
            return ExampleResult(
                example_id=example_id,
                passed=bool(result.get("passed", False)),
                kind=str(result.get("kind", EXAMPLE_KIND_ORACLE)),
                summary=str(result.get("summary", "")),
                details=result.get("details"),
            )
        if result.example_id != example_id:
            return ExampleResult(
                example_id=example_id,
                passed=False,
                kind=result.kind or EXAMPLE_KIND_ORACLE,
                summary=f"mismatched example_id: {result.example_id} != {example_id}",
                details={"returned_example_id": result.example_id},
            )
        return result

    def run_selected_chapters(self, *, chapter_ids: Sequence[str], slow_ok: bool = False) -> list[ExampleResult]:
        _ = slow_ok
        wanted = list(chapter_ids)
        unknown = sorted(set(wanted) - set(self._all_chapter_ids))
        if unknown:
            msg = "unknown chapter_ids: {} (known: {})".format(", ".join(unknown), ", ".join(self._all_chapter_ids))
            raise ValueError(msg)
        cases = [self._load_case(chapter_id) for chapter_id in wanted]
        return [self._safe_run(case) for case in cases]

    def run_all_chapters(self, *, slow_ok: bool = False) -> list[ExampleResult]:
        return self.run_selected_chapters(chapter_ids=self._all_chapter_ids, slow_ok=slow_ok)

    @staticmethod
    def find_first_failure(results: Sequence[ExampleResult]) -> ExampleResult | None:
        return next((result for result in results if not result.passed), None)
