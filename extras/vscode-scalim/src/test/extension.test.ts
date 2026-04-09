import * as assert from "assert";

import { extractPinnedVersion, renderDiagnosticBundle } from "../internal/diagnosticBundle";
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

suite("diagnostic bundle", () => {
	test("extractPinnedVersion parses == constraint", () => {
		assert.strictEqual(extractPinnedVersion("scalim-yaml-dsl-lsp[server]==0.7.5"), "0.7.5");
		assert.strictEqual(extractPinnedVersion("scalim-yaml-dsl-lsp==1.2.3"), "1.2.3");
		assert.strictEqual(extractPinnedVersion("scalim-yaml-dsl-lsp>=1.0.0"), undefined);
	});

	test("renderDiagnosticBundle only prints whitelisted discovery fields", () => {
		const secretYaml = "password: super-secret";
		const bundle = renderDiagnosticBundle({
			timestampIso: "2026-04-08T00:00:00.000Z",
			extensionVersion: "0.0.1",
			vscodeVersion: "1.0.0",
			discovery: {
				projectRoot: "/repo",
				scalimYamlPath: "/repo/scalim.yaml",
				pythonRoots: ["/repo/src"],
				allowedYamlRoots: ["/repo"],
				error: "ok",
				// NOTE: if we accidentally include YAML contents in the future, this should fail.
			},
			lastResolutionTrace: { example: "trace" },
			envKind: "pinnedVenv",
			envMode: "pinnedVenv",
			configuredPinnedServerSpec: "scalim-yaml-dsl-lsp[server]==0.7.5",
			activeServerSpec: "scalim-yaml-dsl-lsp[server]==0.7.5",
			expectedServerVersion: "0.7.5",
			serverPackageVersion: "0.7.5",
			pythonPath: "python3",
			pythonVersion: "3.12.0",
			lspStatus: "running",
			lastStartError: undefined,
			yamlSchemasBound: true,
			yamlSchemasStatus: "ok",
			extensionLogPath: "/logs/extension.log",
			serverLogPath: "/logs/server.log",
		});

		assert.ok(bundle.includes("Scalim Diagnostic Bundle"));
		assert.ok(bundle.includes("projectRoot: /repo"));
		assert.ok(bundle.includes("scalimYamlPath: /repo/scalim.yaml"));
		assert.ok(bundle.includes("This bundle does NOT include YAML file contents."));
		assert.strictEqual(bundle.includes(secretYaml), false);
	});
});
