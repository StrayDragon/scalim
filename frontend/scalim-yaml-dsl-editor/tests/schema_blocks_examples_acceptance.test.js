import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import { parse as parseYaml } from "yaml";

import { indexYamlText, lookupYamlLocation } from "../src/services/yaml_doc.ts";
import { applyBlockAction, buildBlocks } from "../src/libs/schema_blocks/index.ts";

const repoRoot = path.resolve(import.meta.dirname, "..");

const readText = (relPath) => fs.readFileSync(path.join(repoRoot, relPath), "utf8");
const readJson = (relPath) => JSON.parse(readText(relPath));

const walkBlocks = (blocks) => {
  const out = [];
  const stack = [...(blocks || [])];
  while (stack.length) {
    const b = stack.shift();
    if (!b) continue;
    out.push(b);
    if (Array.isArray(b.children) && b.children.length) stack.push(...b.children);
  }
  return out;
};

test("examples acceptance: create missing section + union selector + array insert (public/examples/*.yaml)", () => {
  const schema = readJson("src/schema/demand.gen.json");

  let yamlText = readText("public/examples/minimal.yaml");
  let yamlData = parseYaml(yamlText);
  let { locations } = indexYamlText(yamlText);

  const blocks0 = buildBlocks({ rootSchema: schema, schemaNode: schema, yamlData, yamlLocations: locations });
  const flat0 = walkBlocks(blocks0);

  // Create a missing top-level section (e.g. relations) via ensure_map.
  const relations = flat0.find((b) => b.id === "relations");
  assert.ok(relations, "schema should include relations");
  assert.equal(relations.present, false);
  assert.ok(relations.actions.ensureMap, "relations should support ensureMap");

  const out1 = applyBlockAction(yamlText, relations.actions.ensureMap({ createMissing: true }));
  assert.equal(out1.ok, true);
  assert.ok(out1.text.includes("\nrelations:"), "should create relations section");
  yamlText = out1.text;
  yamlData = parseYaml(yamlText);
  locations = indexYamlText(yamlText).locations;

  // Union selector: outputs[0].container should be inferable by const discriminator (type).
  const blocks1 = buildBlocks({ rootSchema: schema, schemaNode: schema, yamlData, yamlLocations: locations });
  const flat1 = walkBlocks(blocks1);
  const union = flat1.find((b) => b.kind === "union");
  assert.ok(union && union.union, "should find an inferrable union block");
  assert.ok(union.union.inferredOptionId != null, "union should be inferable");
  assert.ok(union.union.options.some((o) => Boolean(o.discriminator)), "union should expose discriminator metadata");

  // Array insert: add a new empty output item (inline mapping) to outputs.
  const outputs = flat1.find((b) => b.id === "outputs" && b.kind === "array");
  assert.ok(outputs && outputs.actions.insertSeqItem, "outputs should support insertSeqItem");
  const idx = outputs.children.length;
  const out2 = applyBlockAction(yamlText, outputs.actions.insertSeqItem(idx, "{}", { valueKind: "inline" }));
  assert.equal(out2.ok, true);
  assert.ok(out2.text.includes("- {}"), "should insert an empty output item");

  // Raw YAML jump locations should resolve for known paths.
  const loc = lookupYamlLocation("outputs.0", locations);
  assert.ok(loc && loc.line >= 1, "should resolve YAML location for outputs.0");
});
