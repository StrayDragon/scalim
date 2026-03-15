from pathlib import Path


def test_demo_big_data_report_selected_chapters_pass() -> None:
    from scalim_misc.demo_big_data_report.chapters.registry import run_selected_chapters

    yaml_path = Path("notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml")
    results = run_selected_chapters(yaml_path=yaml_path, chapter_ids=["basics", "yaml_dsl"])
    for r in results:
        r.raise_if_failed()
