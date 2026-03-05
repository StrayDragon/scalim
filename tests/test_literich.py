from scalim.vendor.literich import Panel, Table


def test_table_render_variants() -> None:
    table = Table(title="Summary")
    table.add_column("Name", max_width=6)
    table.add_column("Value", align="right", formatter=lambda v: f"{v:.1f}")
    table.add_row("rows-long", 3.14)

    rendered = table.render()
    assert "Summary" in rendered
    assert "Name" in rendered
    assert ".." in rendered

    table.border_style = "simple"
    rendered_simple = table.render()
    assert "Summary" in rendered_simple

    table.border_style = "none"
    rendered_none = str(table)
    assert "rows" in rendered_none


def test_panel_render() -> None:
    panel = Panel("Hello", title="Header", width=20, padding=1)
    rendered = panel.render()
    assert "Header" in rendered
    assert "Hello" in rendered
