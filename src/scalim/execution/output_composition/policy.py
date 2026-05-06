from __future__ import absolute_import

from ...typedefs import FailurePolicyValue, parse_failure_policy

_OUTPUT_COMPOSITION_FAILURE_POLICY_LABEL = "output_composition.failure_policy"


def parse_output_failure_policy(value: object) -> FailurePolicyValue:
    return parse_failure_policy(value, label=_OUTPUT_COMPOSITION_FAILURE_POLICY_LABEL)


__all__ = ("parse_output_failure_policy",)
