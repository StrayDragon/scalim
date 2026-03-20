def test_demo_big_data_report_selected_chapters_pass() -> None:
    from notebooks.marimo.demo_big_data_report.chapters.registry import run_selected_chapters

    results = run_selected_chapters(
        chapter_ids=[
            "yaml_dsl_ecommerce",
            "yaml_dsl_ads",
            "yaml_dsl_support",
            "workflow_yaml",
            "workflow_demo_big_data_report",
            "yaml_dsl_debugging",
        ]
    )
    for r in results:
        r.raise_if_failed()
