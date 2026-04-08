export type ImportRootSummary = {
	path: string;
	alias?: string | null;
};

export type DiscoverySummary = {
	projectRoot?: string;
	scalimYamlPath?: string | null;
	pythonRoots?: string[];
	allowedYamlRoots?: string[];
	importRoots?: ImportRootSummary[];
	error?: string;
};

export type DiagnosticBundleInput = {
	timestampIso: string;
	extensionVersion: string;
	vscodeVersion: string;
	envKind?: string;
	envMode?: string;
	pinnedServerSpec?: string;
	expectedServerVersion?: string;
	serverPackageVersion?: string;
	pythonPath?: string;
	pythonVersion?: string;
	lspStatus?: string;
	lastStartError?: string;
	discovery?: DiscoverySummary;
	yamlSchemasBound?: boolean;
	yamlSchemasStatus?: string;
	lastResolutionTrace?: unknown;
	extensionLogPath?: string;
	serverLogPath?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asTrimmedString(value: unknown): string | undefined {
	if (typeof value !== "string") {
		return undefined;
	}
	const text = value.trim();
	return text ? text : undefined;
}

function asStringArray(value: unknown): string[] | undefined {
	if (!Array.isArray(value)) {
		return undefined;
	}
	const out = value
		.filter((item): item is string => typeof item === "string")
		.map((item) => item.trim())
		.filter(Boolean);
	return out.length ? out : undefined;
}

export function extractPinnedVersion(pinnedSpec: string): string | undefined {
	const match = String(pinnedSpec || "").match(/==\s*([0-9A-Za-z][0-9A-Za-z_.-]*)/);
	return match?.[1]?.trim() || undefined;
}

export function summarizeDiscoveryPayload(payload: unknown): DiscoverySummary | undefined {
	if (!isRecord(payload)) {
		return undefined;
	}
	const projectRoot = asTrimmedString(payload["project_root"]);
	const scalimYamlPathRaw = payload["scalim_yaml_path"];
	const scalimYamlPath =
		scalimYamlPathRaw === null ? null : typeof scalimYamlPathRaw === "string" ? scalimYamlPathRaw.trim() : undefined;

	const pythonRoots = asStringArray(payload["python_roots"]);
	const allowedYamlRoots = asStringArray(payload["allowed_yaml_roots"]);
	const error = asTrimmedString(payload["error"]);

	const out: DiscoverySummary = {};
	if (projectRoot) {
		out.projectRoot = projectRoot;
	}
	if (typeof scalimYamlPath === "string" || scalimYamlPath === null) {
		out.scalimYamlPath = scalimYamlPath;
	}
	if (pythonRoots) {
		out.pythonRoots = pythonRoots;
	}
	if (allowedYamlRoots) {
		out.allowedYamlRoots = allowedYamlRoots;
	}
	if (error) {
		out.error = error;
	}
	return out;
}

function safeJson(value: unknown, maxLen = 8000): string {
	try {
		const text = JSON.stringify(value, null, 2);
		if (text.length <= maxLen) {
			return text;
		}
		return text.slice(0, maxLen) + "\n...<truncated>";
	} catch {
		return "<unserializable>";
	}
}

function fmt(value: string | undefined): string {
	return value && value.trim() ? value.trim() : "<unknown>";
}

export function renderDiagnosticBundle(input: DiagnosticBundleInput): string {
	const lines: string[] = [];

	lines.push("Scalim Diagnostic Bundle");
	lines.push(`timestamp: ${fmt(input.timestampIso)}`);
	lines.push(`extensionVersion: ${fmt(input.extensionVersion)}`);
	lines.push(`vscodeVersion: ${fmt(input.vscodeVersion)}`);
	lines.push("");

	lines.push("Environment");
	lines.push(`- envMode: ${fmt(input.envMode)}`);
	lines.push(`- envKind: ${fmt(input.envKind)}`);
	lines.push(`- pinnedServerSpec: ${fmt(input.pinnedServerSpec)}`);
	lines.push(`- expectedServerVersion: ${fmt(input.expectedServerVersion)}`);
	lines.push(`- serverPackageVersion: ${fmt(input.serverPackageVersion)}`);
	lines.push(`- pythonPath: ${fmt(input.pythonPath)}`);
	lines.push(`- pythonVersion: ${fmt(input.pythonVersion)}`);
	lines.push("");

	lines.push("Server");
	lines.push(`- lspStatus: ${fmt(input.lspStatus)}`);
	if (input.lastStartError) {
		lines.push(`- lastStartError: ${input.lastStartError}`);
	} else {
		lines.push("- lastStartError: <none>");
	}
	lines.push("");

	lines.push("Discovery Summary");
	if (!input.discovery) {
		lines.push("- <none>");
	} else {
		if (input.discovery.error) {
			lines.push(`- error: ${input.discovery.error}`);
		}
		lines.push(`- projectRoot: ${fmt(input.discovery.projectRoot)}`);
		lines.push(`- scalimYamlPath: ${input.discovery.scalimYamlPath === null ? "<missing>" : fmt(input.discovery.scalimYamlPath)}`);
		lines.push(`- pythonRoots: ${input.discovery.pythonRoots ? input.discovery.pythonRoots.join(", ") : "<unknown>"}`);
		lines.push(`- allowedYamlRoots: ${input.discovery.allowedYamlRoots ? input.discovery.allowedYamlRoots.join(", ") : "<unknown>"}`);
		if (input.discovery.importRoots && input.discovery.importRoots.length) {
			lines.push("- importRoots:");
			for (const root of input.discovery.importRoots) {
				const alias = root.alias === null ? "<null>" : root.alias ? root.alias : "<none>";
				lines.push(`  - path=${root.path} alias=${alias}`);
			}
		} else {
			lines.push("- importRoots: <unknown>");
		}
	}
	lines.push("");

	lines.push("VSCode Settings");
	lines.push(`- yaml.schemas bound: ${input.yamlSchemasBound === undefined ? "<unknown>" : input.yamlSchemasBound ? "yes" : "no"}`);
	if (input.yamlSchemasStatus) {
		lines.push(`- yaml.schemas status: ${input.yamlSchemasStatus}`);
	}
	lines.push("");

	lines.push("Resolution Trace (last)");
	if (input.lastResolutionTrace === undefined) {
		lines.push("- <none>");
	} else {
		lines.push(safeJson(input.lastResolutionTrace));
	}
	lines.push("");

	lines.push("Logs");
	lines.push(`- extensionLog: ${fmt(input.extensionLogPath)}`);
	lines.push(`- serverLog: ${fmt(input.serverLogPath)}`);
	lines.push("");

	lines.push("Privacy");
	lines.push("- This bundle does NOT include YAML file contents.");
	lines.push("");

	return lines.join("\n");
}

