import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const repoRoot = path.resolve(import.meta.dirname, "..");

const keyPanels = [
  "src/ui/panels/MainSourceFieldsEditor.svelte",
  "src/ui/panels/SourceFieldsEditor.svelte",
  "src/ui/panels/RelationsEditor.svelte",
  "src/ui/panels/SourcesEditor.svelte",
  "src/ui/panels/DerivedFieldsEditor.svelte",
  "src/ui/panels/VisualPanel.svelte"
];

const addButtonPanels = [
  ...keyPanels,
  "src/ui/panels/MainSourceOrderByEditor.svelte",
  "src/ui/panels/OutputFieldsEditor.svelte"
];

const readPanel = (relPath) => fs.readFileSync(path.join(repoRoot, relPath), "utf8");

test("add actions use unified icon buttons with accessible labels", () => {
  const plusOnly = />\s*\+\s*</;
  for (const panel of addButtonPanels) {
    const src = readPanel(panel);
    assert.equal(plusOnly.test(src), false, `${panel} still contains a plus-only add button`);

    const addButtons = [...src.matchAll(/<Button[\s\S]*?variant="add"[\s\S]*?\/>/g)].map((m) => m[0]);
    const addButtonsWithText = [...src.matchAll(/<Button[\s\S]*?variant="add"[\s\S]*?>[\s\S]*?<\/Button>/g)].map((m) => m[0]);

    assert.ok(addButtons.length > 0, `${panel} should render add buttons`);
    assert.equal(addButtonsWithText.length, 0, `${panel} add buttons should be icon-only`);
    for (const btn of addButtons) {
      assert.ok(btn.includes('size="icon"'), `${panel} add button should use size=icon`);
      assert.ok(btn.includes("aria-label="), `${panel} add button should include aria-label`);
      assert.ok(btn.includes("title="), `${panel} add button should include title`);
    }
  }
});

test("key remove actions are not hidden behind hover-only classes", () => {
  for (const panel of keyPanels) {
    const src = readPanel(panel);
    assert.equal(src.includes("group-hover:opacity-100"), false, `${panel} still relies on hover-only visibility`);
    assert.equal(src.includes("opacity-0 transition-opacity"), false, `${panel} still uses hidden-by-default remove buttons`);
  }
});
