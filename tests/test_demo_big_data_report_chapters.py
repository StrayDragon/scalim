def test_demo_big_data_report_selected_chapters_pass() -> None:
    from notebooks.marimo.demo_big_data_report.chapters_of_ir.registry import run_selected_chapters as run_selected_ir_chapters
    from notebooks.marimo.demo_big_data_report.chapters_of_yaml_dsl.registry import (
        run_selected_chapters as run_selected_yaml_dsl_chapters,
    )

    results = run_selected_yaml_dsl_chapters(
        chapter_ids=[
            "yaml_dsl_ecommerce",
            "yaml_dsl_ads",
            "yaml_dsl_support",
            "workflow_yaml",
            "workflow_demo_big_data_report",
            "yaml_dsl_debugging",
        ]
    )
    results.extend(run_selected_ir_chapters(chapter_ids=["ch010_basics", "ch090_guardrails"]))
    for r in results:
        r.raise_if_failed()
