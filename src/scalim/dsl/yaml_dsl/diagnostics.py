from typing import Dict, List


def format_duplicate_effective_field_display_names_message(duplicates: Dict[str, List[str]]) -> str:
    parts: List[str] = []
    for name in sorted(duplicates.keys()):
        parts.append("{!r}: {}".format(name, ", ".join(sorted(duplicates[name]))))

    conflicts = "; ".join(parts)
    hint_tail = "scalim.dsl.yaml_dsl.run/compile(..., demand_diagnostics=DemandDiagnosticsPolicy(validate_unique_field_names=False))."
    hint = "Hint: disable this precheck via runtime entrypoints: {}".format(hint_tail)
    return (
        "Duplicate effective field display names detected while outputs include include_header=true and header_fields_output_by=name. "
        + "Conflicts: {}. {}".format(conflicts, hint)
    )


__all__ = ()
