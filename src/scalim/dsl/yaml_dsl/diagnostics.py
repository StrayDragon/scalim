def format_duplicate_effective_field_display_names_message(duplicates: dict[str, list[str]]) -> str:
    parts: list[str] = []
    for name in sorted(duplicates.keys()):
        parts.append("{!r}: {}".format(name, ", ".join(sorted(duplicates[name]))))

    conflicts = "; ".join(parts)
    hint_tail = (
        "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
        "runtime=DemandRunRuntimeOptions(demand_diagnostics=DemandDiagnosticsPolicy("
        "validate_unique_field_names=False)), ...))."
    )
    hint = f"Hint: disable this precheck via runtime entrypoints: {hint_tail}"
    return (
        "Duplicate effective field display names detected while outputs include include_header=true and header_fields_output_by=name. "
        f"Conflicts: {conflicts}. {hint}"
    )


__all__ = ()
