import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md("# `scalim.execution` 示例")
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    from scalim_misc.examples.public_api.execution import run_public_api_execution

    result = run_public_api_execution()
    mo.md("```\n{}\n```".format(result.summary))
    return result


if __name__ == "__main__":
    app.run()
