import assert from "node:assert/strict";
import test from "node:test";

import { detachAliasAtPath, setScalarAtPathDeep } from "../src/services/yaml_patch.ts";
import { findUnknownFields } from "../src/services/unknown_fields.ts";

test("setScalarAtPathDeep: safe scalar patch preserves anchors + header comments", () => {
  const input = [
    "# header",
    "# note",
    "",
    "name: demo",
    "",
    "main_source:",
    "  source_id: orders",
    '  loader: "mod:fn"',
    "  fields:",
    "    order_id: &order_id",
    "      field: order_id",
    "      name: 订单ID",
    "",
    "output:",
    "  path: ./out.csv",
    ""
  ].join("\n");

  const out = setScalarAtPathDeep(input, ["main_source", "fields", "order_id", "name"], "订单ID2", { createMissing: true });
  assert.equal(out.ok, true);
  assert.equal(out.plan.kind, "safe");
  assert.ok(out.text.includes("&order_id"));
  assert.ok(out.text.startsWith("# header\n# note\n\n"));
  assert.ok(out.text.includes("name: 订单ID2"));
});

test("setScalarAtPathDeep: edits through alias require a decision", () => {
  const input = [
    "# header",
    "",
    "name: alias_demo",
    "_templates:",
    "  order_id: &t_order_id",
    "    field: order_id",
    "    name: 订单ID",
    "",
    "main_source:",
    "  source_id: orders",
    '  loader: "mod:fn"',
    "  fields:",
    "    order_id: *t_order_id",
    "",
    "output:",
    "  path: ./out.csv",
    ""
  ].join("\n");

  const out = setScalarAtPathDeep(input, ["main_source", "fields", "order_id", "name"], "订单ID2", { createMissing: true });
  assert.equal(out.ok, true);
  assert.equal(out.plan.kind, "rewrite");
  assert.ok(out.decision);
  assert.equal(out.decision.kind, "alias");
  assert.equal(out.decision.alias.anchorName, "t_order_id");
  assert.deepEqual(out.decision.alias.aliasPath, ["main_source", "fields", "order_id"]);
  assert.deepEqual(out.decision.alias.remainingPath, ["name"]);
  assert.deepEqual(out.decision.alias.anchorPath, ["_templates", "order_id"]);
  assert.equal(out.text, input);
});

test("detachAliasAtPath: expands mapping alias in-place (rewrite plan)", () => {
  const input = [
    "name: alias_demo",
    "_templates:",
    "  order_id: &t_order_id",
    "    field: order_id",
    "    name: 订单ID",
    "",
    "main_source:",
    "  source_id: orders",
    '  loader: "mod:fn"',
    "  fields:",
    "    order_id: *t_order_id",
    "",
    "output:",
    "  path: ./out.csv",
    ""
  ].join("\n");

  const out = detachAliasAtPath(input, ["main_source", "fields", "order_id"]);
  assert.equal(out.ok, true);
  assert.equal(out.plan.kind, "rewrite");
  assert.ok(out.text.includes("order_id:\n      field: order_id\n      name: 订单ID"));
  assert.ok(!out.text.includes("order_id: *t_order_id"));
});

test("findUnknownFields: ignores YAML merge key (<<)", () => {
  const schema = {
    type: "object",
    properties: {
      main_source: {
        type: "object",
        properties: {
          fields: {
            type: "object",
            additionalProperties: {
              type: "object",
              properties: {
                name: { type: "string" },
                field: { type: "string" },
                source: { type: "string" }
              },
              additionalProperties: false
            }
          }
        }
      }
    },
    additionalProperties: false
  };

  const yamlData = {
    main_source: {
      fields: {
        order_id: {
          "<<": "*base",
          name: "覆盖名称"
        }
      }
    }
  };

  const unknown = findUnknownFields(yamlData, schema);
  assert.deepEqual(
    unknown.map((u) => u.field),
    []
  );
});

