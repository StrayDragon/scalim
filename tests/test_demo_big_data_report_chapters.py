def test_demo_big_data_report_selected_chapters_pass() -> None:
    from notebooks.marimo.demo_big_data_report.chapters.registry import run_selected_chapters

    results = run_selected_chapters(chapter_ids=["basics", "yaml_dsl"])
    for r in results:
        r.raise_if_failed()
