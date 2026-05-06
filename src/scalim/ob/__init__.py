"""可观测性入口."""

# pragma: scalim-public-api tier1:100:scalim.ob|可观测性入口|构建 observer manager / 采集事件

from .._internal.utils.loader_result import LoaderResultPolicy
from ._internal.common import CaptureOverflowPolicy, ObserverManagerMode
from .observability import Observability, ObservabilityOptions

__all__ = (
    "CaptureOverflowPolicy",
    "LoaderResultPolicy",
    "Observability",
    "ObservabilityOptions",
    "ObserverManagerMode",
)
