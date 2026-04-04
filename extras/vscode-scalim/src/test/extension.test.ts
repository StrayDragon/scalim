import * as assert from "assert";

import { mergeYamlSchemas } from "../internal/yamlSchemas";

suite("yaml.schemas merge", () => {
	test("adds scalim mappings without touching existing keys", () => {
		const existing = {
			"http://example.com/schema": ["a.yaml"],
		};
		const merged = mergeYamlSchemas(existing, {
			"/abs/scalim.json": ["scalim.yaml"],
		});
		assert.deepStrictEqual(merged["http://example.com/schema"], ["a.yaml"]);
		assert.deepStrictEqual(merged["/abs/scalim.json"], ["scalim.yaml"]);
	});

	test("is idempotent and merges patterns", () => {
		const existing = {
			"/abs/scalim.json": ["scalim.yaml"],
		};
		const merged = mergeYamlSchemas(existing, {
			"/abs/scalim.json": ["scalim.yaml", "demand/**/*.y*ml"],
		});
		assert.deepStrictEqual(merged["/abs/scalim.json"], ["scalim.yaml", "demand/**/*.y*ml"]);
	});
});
