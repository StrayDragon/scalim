from typing import TYPE_CHECKING

from ....planning.plan import ExecutionPlan
from ..policy import AdaptivePolicy
from ..tuning import AdaptiveTuning

if TYPE_CHECKING:
    from ...pipeline.overrides import PipelineOverrides


class AdaptiveLoadRefSchedulerBase(object):
    def _require_plan(self) -> ExecutionPlan:  # pragma: no cover  # pragma: allow-no-cover abstract method
        raise NotImplementedError

    def _require_overrides(self) -> "PipelineOverrides":  # pragma: no cover  # pragma: allow-no-cover abstract method
        raise NotImplementedError

    def _require_tuning(self) -> AdaptiveTuning:  # pragma: no cover  # pragma: allow-no-cover abstract method
        raise NotImplementedError

    def _require_policy(self) -> AdaptivePolicy:  # pragma: no cover  # pragma: allow-no-cover abstract method
        raise NotImplementedError


__all__ = ()
