import assert from "node:assert/strict";
import test from "node:test";

import { parse as parseYaml } from "yaml";

import { indexYamlText } from "../src/services/yaml_doc.ts";
import { applyBlockAction, buildBlocks, OverrideRegistry } from "../src/libs/schema_blocks/index.ts";

test("buildBlocks: required ordering + id stability + description/title", () => {
  const schema = {
    type: "object",
    properties: {
      name: { type: "string", description: "Report name" },
      mode: { title: "Mode", enum: ["a", "b"] },
      tags: { type: "object", additionalProperties: { type: "string", description: "Tag value" } },
      items: { type: "array", items: { type: "string", description: "Item value" } }
    },
    required: ["mode", "name"],
    additionalProperties: false
  };

  const yamlText = ["name: demo", "mode: a", "tags:", "  k1: v1", "items:", "  - x", "  - y", ""].join("\n");
  const yamlData = parseYaml(yamlText);
  const { locations } = indexYamlText(yamlText);

  const blocks = buildBlocks({ rootSchema: schema, schemaNode: schema, yamlData, yamlLocations: locations });

  // Required fields appear before optional fields.
  const requiredBlocks = blocks.filter((b) => b.required);
  const optionalBlocks = blocks.filter((b) => !b.required);
  assert.equal(requiredBlocks.length, 2);
  assert.equal(optionalBlocks.length, 2);
  assert.ok(blocks.indexOf(requiredBlocks[0]) < blocks.indexOf(optionalBlocks[0]));

  const nameBlock = blocks.find((b) => b.yamlPath.join(".") === "name");
  assert.ok(nameBlock);
  assert.equal(nameBlock.id, "name");
  assert.equal(nameBlock.kind, "scalar");
  assert.equal(nameBlock.required, true);
  assert.equal(nameBlock.description, "Report name");

  const modeBlock = blocks.find((b) => b.yamlPath.join(".") === "mode");
  assert.ok(modeBlock);
  assert.equal(modeBlock.kind, "enum");
  assert.equal(modeBlock.title, "Mode");

  const tagsBlock = blocks.find((b) => b.yamlPath.join(".") === "tags");
  assert.ok(tagsBlock);
  assert.equal(tagsBlock.kind, "map");
  assert.ok(tagsBlock.map);
  assert.deepEqual(tagsBlock.map.keys, ["k1"]);
  assert.equal(tagsBlock.children.length, 1);
  assert.equal(tagsBlock.children[0].id, "tags.k1");
  assert.equal(tagsBlock.children[0].kind, "scalar");

  const itemsBlock = blocks.find((b) => b.yamlPath.join(".") === "items");
  assert.ok(itemsBlock);
  assert.equal(itemsBlock.kind, "array");
  assert.equal(itemsBlock.children.length, 2);
  assert.equal(itemsBlock.children[0].id, "items.0");
  assert.equal(itemsBlock.children[1].id, "items.1");
});

test("buildBlocks: $ref + allOf expansion builds children", () => {
  const schema = {
    type: "object",
    properties: {
      config: { $ref: "#/definitions/Config" }
    },
    required: ["config"],
    definitions: {
      Config: {
        allOf: [
          { type: "object", properties: { enabled: { type: "boolean" } }, required: ["enabled"] },
          { type: "object", properties: { threshold: { type: "number", description: "th" } } }
        ]
      }
    }
  };

  const yamlText = ["config:", "  enabled: true", "  threshold: 0.5", ""].join("\n");
  const yamlData = parseYaml(yamlText);
  const { locations } = indexYamlText(yamlText);

  const blocks = buildBlocks({ rootSchema: schema, schemaNode: schema, yamlData, yamlLocations: locations });
  const config = blocks.find((b) => b.id === "config");
  assert.ok(config);
  assert.equal(config.kind, "object");
  assert.ok(config.children.find((c) => c.id === "config.enabled" && c.required === true));
  assert.ok(config.children.find((c) => c.id === "config.threshold" && c.description === "th"));
});

test("OverrideRegistry: exact beats glob; priority beats lower; override defaults to no children", () => {
  const schema = {
    type: "object",
    properties: {
      a: {
        type: "object",
        properties: { b: { type: "string" } }
      }
    }
  };
  const yamlText = ["a:", "  b: x", ""].join("\n");
  const yamlData = parseYaml(yamlText);
  const { locations } = indexYamlText(yamlText);

  const overrides = new OverrideRegistry();
  overrides.registerGlob("*", {
    id: "glob",
    priority: 1000,
    build: (ctx) => ({
      id: ctx.yamlPath.join("."),
      yamlPath: ctx.yamlPath,
      kind: "custom",
      title: "glob",
      description: "",
      required: ctx.required,
      present: ctx.present,
      schemaNode: ctx.schemaNodeInfo,
      actions: ctx.actions,
      children: []
    })
  });
  overrides.registerExact(["a"], {
    id: "exact",
    priority: 0,
    build: (ctx) => ({
      id: ctx.yamlPath.join("."),
      yamlPath: ctx.yamlPath,
      kind: "custom",
      title: "exact",
      description: "",
      required: ctx.required,
      present: ctx.present,
      schemaNode: ctx.schemaNodeInfo,
      actions: ctx.actions,
      children: []
    })
  });

  const blocks = buildBlocks({ rootSchema: schema, schemaNode: schema, yamlData, yamlLocations: locations, overrides });
  const a = blocks.find((b) => b.id === "a");
  assert.ok(a);
  assert.equal(a.kind, "custom");
  assert.equal(a.title, "exact");
  assert.equal(a.children.length, 0);
});

test("union inference: inferrable -> union selector; not inferrable -> unsupported + raw YAML fallback", () => {
  const schema = {
    type: "object",
    properties: {
      union_ok: {
        oneOf: [
          {
            type: "object",
            properties: { kind: { const: "a" }, a: { type: "string" } },
            required: ["kind"]
          },
          {
            type: "object",
            properties: { kind: { const: "b" }, b: { type: "string" } },
            required: ["kind"]
          }
        ]
      },
      union_bad: {
        oneOf: [
          { type: "object", properties: { a: { type: "string" } }, required: ["a"] },
          { type: "object", properties: { b: { type: "string" } }, required: ["b"] }
        ]
      }
    }
  };

  const yamlText = ["union_ok:", "  kind: a", "  a: x", "union_bad:", "  c: 1", ""].join("\n");
  const yamlData = parseYaml(yamlText);
  const { locations } = indexYamlText(yamlText);

  const blocks = buildBlocks({ rootSchema: schema, schemaNode: schema, yamlData, yamlLocations: locations });
  const ok = blocks.find((b) => b.id === "union_ok");
  assert.ok(ok);
  assert.equal(ok.kind, "union");
  assert.ok(ok.union);
  assert.equal(ok.union.inferredOptionId, "0");
  assert.equal(ok.union.options.length, 2);

  const bad = blocks.find((b) => b.id === "union_bad");
  assert.ok(bad);
  assert.equal(bad.kind, "unsupported");
  assert.ok(bad.unsupported);
  assert.deepEqual(bad.unsupported.rawYamlPath, ["union_bad"]);
});

test("BlockAction mapping: safe patch vs alias decision (rewrite)", () => {
  const safeInput = ["name: demo", ""].join("\n");
  const safeOut = applyBlockAction(safeInput, { kind: "set", path: ["name"], value: "demo2", createMissing: true });
  assert.equal(safeOut.ok, true);
  assert.equal(safeOut.plan.kind, "safe");
  assert.ok(safeOut.text.includes("name: demo2"));

  const aliasInput = [
    "name: alias_demo",
    "_templates:",
    "  order_id: &t_order_id",
    "    field: order_id",
    "    name: 订单ID",
    "",
    "main_source:",
    "  fields:",
    "    order_id: *t_order_id",
    ""
  ].join("\n");
  const aliasOut = applyBlockAction(aliasInput, {
    kind: "set",
    path: ["main_source", "fields", "order_id", "name"],
    value: "订单ID2",
    createMissing: true
  });
  assert.equal(aliasOut.ok, true);
  assert.equal(aliasOut.plan.kind, "rewrite");
  assert.ok(aliasOut.decision);
  assert.equal(aliasOut.decision.kind, "alias");
});
