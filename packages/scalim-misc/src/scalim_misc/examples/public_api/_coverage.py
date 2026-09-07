from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class PublicAllCoverage:
    module_name: str
    declared_all: tuple[str, ...]
    covered: tuple[str, ...]
    missing: tuple[str, ...]
    stale: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing and not self.stale


def _sorted_tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def check_public_all_coverage(module: Any, *, covered: set[str]) -> PublicAllCoverage:
    declared_all = _sorted_tuple(getattr(module, "__all__", ()))
    covered_tuple = _sorted_tuple(covered)
    declared_set = set(declared_all)
    missing = _sorted_tuple(declared_set - set(covered_tuple))
    stale = _sorted_tuple(set(covered_tuple) - declared_set)
    return PublicAllCoverage(
        module_name=str(getattr(module, "__name__", type(module).__name__)),
        declared_all=declared_all,
        covered=covered_tuple,
        missing=missing,
        stale=stale,
    )


def coverage_failure_summary(coverage: PublicAllCoverage) -> str:
    parts: list[str] = []
    if coverage.missing:
        parts.append("missing: {}".format(", ".join(coverage.missing)))
    if coverage.stale:
        parts.append("stale: {}".format(", ".join(coverage.stale)))
    return "{}.__all__ coverage failed ({})".format(coverage.module_name, "; ".join(parts) or "unknown")


def coverage_to_details(coverage: PublicAllCoverage) -> dict[str, Any]:
    return {
        "module": coverage.module_name,
        "declared_all": list(coverage.declared_all),
        "covered": list(coverage.covered),
        "missing": list(coverage.missing),
        "stale": list(coverage.stale),
    }
