import * as fs from "node:fs";
import * as fsp from "node:fs/promises";
import * as path from "node:path";

import * as vscode from "vscode";
import {
	LanguageClient,
	type LanguageClientOptions,
	type ServerOptions,
	State,
} from "vscode-languageclient/node";

import { runCommand } from "./internal/exec";
import { mergeYamlSchemas } from "./internal/yamlSchemas";

const DEFAULT_PINNED_SERVER_SPEC = "scalim-yaml-dsl-lsp[server]==0.7.5";
const DEFAULT_ENV_MODE = "auto";
const DEFAULT_WORKSPACE_VENV_PATH = ".venv";

type EnvMode = "pinnedVenv" | "workspaceVenv" | "auto";

type Semver = {
	major: number;
	minor: number;
	patch: number;
};

type ProvisionedEnv = {
	kind: "pinnedVenv" | "workspaceVenv" | "path";
	pinnedServerSpec: string;
	pythonPath: string;
	pythonVersion: string;
	venvPath: string;
	venvPythonPath: string;
	scalimCliPath: string;
	scalimYamlDslLspPath: string;
	serverPackageVersion?: string;
	schemaPaths?: {
		scalimYaml: string;
		demand: string;
		workflow: string;
	};
	schemaRequiredKeys?: {
		demand: string[];
		workflow: string[];
	};
};

let currentClient: LanguageClient | undefined;
let currentEnv: ProvisionedEnv | undefined;
let expectedStop = false;
let startMutex: Promise<void> | undefined;
let statusBarItem: vscode.StatusBarItem | undefined;
let lastStartError: string | undefined;
let lastProjectRoot: string | undefined;
let autoStartAttempted = false;

function ensureStatusBar(context: vscode.ExtensionContext): vscode.StatusBarItem {
	if (statusBarItem) {
		return statusBarItem;
	}

	const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
	item.command = "scalim.yamlDsl.showDiagnostics";
	item.text = "Scalim YAML DSL";
	item.tooltip = "Scalim YAML DSL";
	item.show();

	context.subscriptions.push(item);
	statusBarItem = item;
	return item;
}

function setStatusBarState(
	context: vscode.ExtensionContext,
	status: "starting" | "running" | "stopped",
	env: ProvisionedEnv | undefined,
): void {
	const item = ensureStatusBar(context);

	const version = env?.serverPackageVersion ?? "<unknown>";
	const projectRoot = lastProjectRoot ?? "<unknown>";
	const projectRootBase = projectRoot !== "<unknown>" ? path.basename(projectRoot) : "";

	if (status === "starting") {
		item.text = "$(sync~spin) Scalim YAML DSL";
	} else if (status === "running") {
		item.text = `$(check) Scalim YAML DSL ${version}${projectRootBase ? ` · ${projectRootBase}` : ""}`;
	} else {
		item.text = "$(error) Scalim YAML DSL stopped";
	}

	const tooltip = [
		"Scalim YAML DSL",
		`status=${status}`,
		`serverVersion=${version}`,
		`projectRoot=${projectRoot}`,
		env ? `envKind=${env.kind}` : undefined,
		env ? `venvPath=${env.venvPath}` : "venvPath=<unknown>",
		lastStartError ? `lastStartError=${lastStartError}` : undefined,
	]
		.filter((line): line is string => Boolean(line))
		.join("\n");
	item.tooltip = tooltip;
	item.show();
}

function isWindows(): boolean {
	return process.platform === "win32";
}

function getVenvScriptsDir(venvPath: string): string {
	return path.join(venvPath, isWindows() ? "Scripts" : "bin");
}

function findVenvExecutable(venvPath: string, baseName: string): string | undefined {
	const scriptsDir = getVenvScriptsDir(venvPath);
	const candidates = isWindows()
		? [baseName + ".exe", baseName + ".cmd", baseName + ".bat", baseName]
		: [baseName];

	for (const name of candidates) {
		const candidate = path.join(scriptsDir, name);
		if (fs.existsSync(candidate)) {
			return candidate;
		}
	}
	return undefined;
}

function parseSemver(text: string): Semver | undefined {
	const match = text.trim().match(/^(\d+)\.(\d+)\.(\d+)/);
	if (!match) {
		return undefined;
	}
	return {
		major: Number(match[1]),
		minor: Number(match[2]),
		patch: Number(match[3]),
	};
}

function satisfiesPython310(version: Semver): boolean {
	return version.major > 3 || (version.major === 3 && version.minor >= 10);
}

function summarizeArgs(args: readonly unknown[]): string {
	try {
		const text = JSON.stringify(args);
		if (text.length <= 300) {
			return text;
		}
		return text.slice(0, 300) + "...";
	} catch {
		return "<unserializable>";
	}
}

function isScalimCommandId(commandId: string | undefined): boolean {
	return Boolean(commandId && commandId.startsWith("scalim."));
}

function friendlyActionTitle(title: string, commandId: string | undefined): string {
	if (!isScalimCommandId(commandId)) {
		return title;
	}
	if (title.startsWith("Scalim:")) {
		return title;
	}
	return `Scalim: ${title}`;
}

function getExtensionConfig(): {
	envMode: EnvMode;
	workspaceVenvPath: string;
	pythonPathOverride?: string;
	pinnedServerSpec: string;
	autoSchemaBinding: boolean;
} {
	const cfg = vscode.workspace.getConfiguration("scalim.yamlDsl");
	const envModeRaw = (cfg.get<string>("envMode") || "").trim() || DEFAULT_ENV_MODE;
	const envMode: EnvMode =
		envModeRaw === "workspaceVenv" || envModeRaw === "auto" || envModeRaw === "pinnedVenv" ? envModeRaw : "pinnedVenv";
	const workspaceVenvPath = (cfg.get<string>("workspaceVenvPath") || "").trim() || DEFAULT_WORKSPACE_VENV_PATH;
	const pythonPathOverride = (cfg.get<string>("pythonPath") || "").trim() || undefined;
	const pinnedServerSpec = (cfg.get<string>("pinnedServerSpec") || "").trim() || DEFAULT_PINNED_SERVER_SPEC;
	const autoSchemaBinding = cfg.get<boolean>("autoSchemaBinding", true);
	return { envMode, workspaceVenvPath, pythonPathOverride, pinnedServerSpec, autoSchemaBinding };
}

async function detectPython(
	output: vscode.OutputChannel,
	pythonPathOverride?: string,
): Promise<{ pythonPath: string; pythonVersion: Semver; pythonVersionRaw: string } | undefined> {
	const candidates = pythonPathOverride
		? [pythonPathOverride]
		: isWindows()
			? ["python", "python3", "py"]
			: ["python3", "python"];

	output.appendLine(`[python] Detecting python (>=3.10). Candidates: ${candidates.join(", ")}`);

	for (const candidate of candidates) {
		const result = await runCommand(candidate, ["-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"]);
		const combined = (result.stdout || result.stderr).trim();
		const semver = parseSemver(combined);
		if (!semver) {
			output.appendLine(`[python] ${candidate}: unable to parse version from: ${JSON.stringify(combined)}`);
			continue;
		}
		output.appendLine(`[python] ${candidate}: ${semver.major}.${semver.minor}.${semver.patch}`);
		if (!satisfiesPython310(semver)) {
			output.appendLine(`[python] ${candidate}: version too old (need >=3.10)`);
			continue;
		}
		return { pythonPath: candidate, pythonVersion: semver, pythonVersionRaw: combined };
	}

	return undefined;
}

function resolveWorkspaceRoot(): string | undefined {
	return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

const YAML_DSL_SCHEMA_MARKERS = ["demand.gen.json", "workflow.gen.json", "scalim_yaml.gen.json"] as const;

function escapeRegExp(text: string): string {
	return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function hasRequiredKeys(text: string, requiredKeys: readonly string[]): boolean {
	return requiredKeys.every((key) => new RegExp(`^\\s*${escapeRegExp(key)}\\s*:`, "m").test(text));
}

function hasWorkflowMapping(text: string): boolean {
	const lines = text.split(/\r?\n/);
	for (let i = 0; i < lines.length; i++) {
		const line = lines[i];
		if (!/^\s*workflow\s*:/.test(line)) {
			continue;
		}

		const rest = line.replace(/^\s*workflow\s*:/, "").trim();
		if (rest.startsWith("{")) {
			return true;
		}
		if (rest.startsWith("[")) {
			return false;
		}
		if (rest) {
			return false;
		}

		for (let j = i + 1; j < lines.length; j++) {
			const next = lines[j];
			const trimmed = next.trim();
			if (!trimmed || trimmed.startsWith("#")) {
				continue;
			}
			if (trimmed.startsWith("-")) {
				return false;
			}
			return trimmed.includes(":");
		}

		return true;
	}

	return false;
}

function documentPreviewText(document: vscode.TextDocument, maxLines = 200): string {
	const endLine = Math.min(document.lineCount, Math.max(1, maxLines));
	const endPos = new vscode.Position(endLine, 0);
	return document.getText(new vscode.Range(new vscode.Position(0, 0), endPos));
}

function isLikelyScalimYamlDslDocument(document: vscode.TextDocument): boolean {
	if (document.languageId !== "yaml") {
		return false;
	}

	if (document.uri.scheme === "file") {
		const fsPath = document.uri.fsPath;
		if (path.basename(fsPath) === "scalim.yaml") {
			return false;
		}
		if (fsPath.split(path.sep).includes(".tmp")) {
			return false;
		}
	}

	const text = documentPreviewText(document);
	if (!text.trim()) {
		return false;
	}

	if (YAML_DSL_SCHEMA_MARKERS.some((marker) => text.includes(marker))) {
		return true;
	}
	if (text.includes("$import") || text.includes("$init_var")) {
		return true;
	}
	if (/^\s*(loader|call_by)\s*:/m.test(text)) {
		return true;
	}
	if (/^imports\s*:/m.test(text) && /^name\s*:/m.test(text)) {
		return true;
	}
	if (hasWorkflowMapping(text)) {
		return true;
	}
	if (hasRequiredKeys(text, ["name", "main_source"])) {
		return true;
	}
	return false;
}

function guessYamlDslKindFromText(
	text: string,
	schemaRequiredKeys?: { demand: readonly string[]; workflow: readonly string[] },
): "demand" | "workflow" {
	const workflowRequired = schemaRequiredKeys?.workflow ?? ["workflow"];
	const demandRequired = schemaRequiredKeys?.demand ?? ["name", "main_source"];

	if (hasRequiredKeys(text, workflowRequired) && hasWorkflowMapping(text)) {
		return "workflow";
	}
	if (hasRequiredKeys(text, demandRequired)) {
		return "demand";
	}

	if (text.includes("workflow.gen.json")) {
		return "workflow";
	}
	return "demand";
}

function resolveWorkspaceVenvPath(workspaceRoot: string, configuredVenvPath: string): string {
	const raw = configuredVenvPath.trim() || DEFAULT_WORKSPACE_VENV_PATH;
	if (path.isAbsolute(raw)) {
		return raw;
	}
	return path.join(workspaceRoot, raw);
}

async function resolvePathEnv(output: vscode.OutputChannel): Promise<ProvisionedEnv | undefined> {
	const scalimYamlDslLspPath = "scalim-yaml-dsl-lsp";
	const lspHelp = await runCommand(scalimYamlDslLspPath, ["--help"]);
	if (lspHelp.exitCode !== 0) {
		output.appendLine("[path] scalim-yaml-dsl-lsp not found in PATH.");
		return undefined;
	}

	const scalimCliPath = "scalim-cli";
	const cliHelp = await runCommand(scalimCliPath, ["--help"]);
	if (cliHelp.exitCode !== 0) {
		output.appendLine("[path] scalim-cli not found in PATH; schema binding will be skipped.");
	}

	output.appendLine(`[path] Using PATH commands: ${scalimYamlDslLspPath} / ${scalimCliPath}`);

	return {
		kind: "path",
		pinnedServerSpec: "<PATH>",
		pythonPath: "<PATH>",
		pythonVersion: "<unknown>",
		venvPath: "<PATH>",
		venvPythonPath: "<unknown>",
		scalimCliPath,
		scalimYamlDslLspPath,
		serverPackageVersion: undefined,
	};
}

async function resolveWorkspaceVenvEnv(
	output: vscode.OutputChannel,
	workspaceRoot: string,
	configuredVenvPath: string,
): Promise<ProvisionedEnv | undefined> {
	const venvPath = resolveWorkspaceVenvPath(workspaceRoot, configuredVenvPath);
	if (!fs.existsSync(venvPath)) {
		output.appendLine(`[workspace] workspaceVenvPath not found: ${venvPath}`);
		return undefined;
	}

	const venvPythonPath =
		findVenvExecutable(venvPath, "python") ??
		findVenvExecutable(venvPath, "python3") ??
		path.join(getVenvScriptsDir(venvPath), isWindows() ? "python.exe" : "python");
	if (!fs.existsSync(venvPythonPath)) {
		output.appendLine(`[workspace] Missing python in workspace venv: ${venvPythonPath}`);
		return undefined;
	}

	const pythonVersionResult = await runCommand(venvPythonPath, ["-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"]);
	const pythonVersionRaw = (pythonVersionResult.stdout || pythonVersionResult.stderr).trim();
	const pythonVersion = parseSemver(pythonVersionRaw);
	if (!pythonVersion) {
		output.appendLine(`[workspace] Unable to parse python version from: ${JSON.stringify(pythonVersionRaw)}`);
		return undefined;
	}
	if (!satisfiesPython310(pythonVersion)) {
		output.appendLine(`[workspace] Python version too old (need >=3.10): ${pythonVersion.major}.${pythonVersion.minor}.${pythonVersion.patch}`);
		return undefined;
	}

	const scalimCliPath = findVenvExecutable(venvPath, "scalim-cli");
	const scalimYamlDslLspPath = findVenvExecutable(venvPath, "scalim-yaml-dsl-lsp");
	if (!scalimCliPath || !scalimYamlDslLspPath) {
		output.appendLine(`[workspace] Missing expected executables in workspace venv scripts dir: ${getVenvScriptsDir(venvPath)}`);
		output.appendLine(`[workspace] scalim-cli: ${scalimCliPath ?? "<missing>"}`);
		output.appendLine(`[workspace] scalim-yaml-dsl-lsp: ${scalimYamlDslLspPath ?? "<missing>"}`);
		return undefined;
	}

	const showResult = await runCommand(venvPythonPath, ["-m", "pip", "show", "scalim-yaml-dsl-lsp"], { cwd: workspaceRoot });
	const serverPackageVersion = showResult.stdout
		.split(/\r?\n/g)
		.map((line) => line.trim())
		.find((line) => line.toLowerCase().startsWith("version:"))
		?.split(":", 2)[1]
		?.trim();

	output.appendLine(`[workspace] Using workspace venv: ${venvPath}`);
	output.appendLine(`[workspace] python=${venvPythonPath} version=${pythonVersionRaw}`);
	output.appendLine(`[workspace] scalim-cli=${scalimCliPath}`);
	output.appendLine(`[workspace] scalim-yaml-dsl-lsp=${scalimYamlDslLspPath}`);

	return {
		kind: "workspaceVenv",
		pinnedServerSpec: "<workspaceVenv>",
		pythonPath: venvPythonPath,
		pythonVersion: pythonVersionRaw,
		venvPath,
		venvPythonPath,
		scalimCliPath,
		scalimYamlDslLspPath,
		serverPackageVersion,
	};
}

async function ensureVenv(
	context: vscode.ExtensionContext,
	output: vscode.OutputChannel,
	pythonPath: string,
	pinnedServerSpec: string,
	allowInstall: boolean,
): Promise<ProvisionedEnv> {
	const storagePath = context.globalStorageUri.fsPath;
	const venvPath = path.join(storagePath, "scalim-yaml-dsl-lsp-venv");
	const metaPath = path.join(storagePath, "scalim-yaml-dsl-lsp.meta.json");

	await fsp.mkdir(storagePath, { recursive: true });

	const venvPythonPath =
		findVenvExecutable(venvPath, "python") ??
		findVenvExecutable(venvPath, "python3") ??
		path.join(getVenvScriptsDir(venvPath), isWindows() ? "python.exe" : "python");

	const needCreate = !fs.existsSync(venvPythonPath);
	if (needCreate && !allowInstall) {
		output.appendLine("[venv] pinned venv missing; install is disabled (need explicit user action).");
		throw new Error("Pinned venv is not provisioned");
	}
	if (needCreate) {
		output.appendLine(`[venv] Creating venv at ${venvPath}`);
		const result = await runCommand(pythonPath, ["-m", "venv", venvPath], { cwd: storagePath });
		if (result.exitCode !== 0) {
			output.appendLine(`[venv] Failed to create venv (exit=${result.exitCode})`);
			output.appendLine(result.stderr.trim());
			throw new Error("Failed to create venv");
		}
	} else {
		output.appendLine(`[venv] Reusing venv at ${venvPath}`);
	}

	let needInstall = true;
	if (!needCreate && fs.existsSync(metaPath)) {
		try {
			const raw = await fsp.readFile(metaPath, "utf8");
			const meta = JSON.parse(raw) as unknown;
			if (typeof meta === "object" && meta !== null) {
				const pythonPathMeta = String((meta as Record<string, unknown>)["pythonPath"] ?? "");
				const pinnedServerSpecMeta = String((meta as Record<string, unknown>)["pinnedServerSpec"] ?? "");
				if (pythonPathMeta === pythonPath && pinnedServerSpecMeta === pinnedServerSpec) {
					needInstall = false;
				}
			}
		} catch (e) {
			output.appendLine(`[venv] Failed to read/parse meta; will reinstall pinned server. err=${String(e)}`);
		}
	}

	if (needInstall && !allowInstall) {
		output.appendLine("[pip] pinned server not installed or meta mismatch; install is disabled (need explicit user action).");
		throw new Error("Pinned server is not provisioned");
	}

	if (needInstall) {
		const installArgs = ["-m", "pip", "install", "--upgrade", pinnedServerSpec];
		output.appendLine(`[pip] Installing pinned server: ${pinnedServerSpec}`);
		output.appendLine(`[pip] Command: ${venvPythonPath} ${installArgs.join(" ")}`);
		const installResult = await runCommand(venvPythonPath, installArgs, { cwd: storagePath });
		if (installResult.exitCode !== 0) {
			output.appendLine(`[pip] Install failed (exit=${installResult.exitCode})`);
			output.appendLine(installResult.stderr.trim());
			throw new Error("Failed to install pinned server");
		}
	} else {
		output.appendLine(`[pip] Reusing pinned server install: ${pinnedServerSpec}`);
	}

	const showResult = await runCommand(venvPythonPath, ["-m", "pip", "show", "scalim-yaml-dsl-lsp"], { cwd: storagePath });
	const serverPackageVersion = showResult.stdout
		.split(/\r?\n/g)
		.map((line) => line.trim())
		.find((line) => line.toLowerCase().startsWith("version:"))
		?.split(":", 2)[1]
		?.trim();

	const scalimCliPath = findVenvExecutable(venvPath, "scalim-cli");
	const scalimYamlDslLspPath = findVenvExecutable(venvPath, "scalim-yaml-dsl-lsp");
	if (!scalimCliPath || !scalimYamlDslLspPath) {
		output.appendLine(`[venv] Missing expected executables in venv scripts dir: ${getVenvScriptsDir(venvPath)}`);
		output.appendLine(`[venv] scalim-cli: ${scalimCliPath ?? "<missing>"}`);
		output.appendLine(`[venv] scalim-yaml-dsl-lsp: ${scalimYamlDslLspPath ?? "<missing>"}`);
		throw new Error("Pinned server install is missing CLI entrypoints");
	}

	const pythonVersionResult = await runCommand(venvPythonPath, ["-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"]);
	const pythonVersionRaw = (pythonVersionResult.stdout || pythonVersionResult.stderr).trim();

	const meta = {
		pythonPath,
		pythonVersion: pythonVersionRaw,
		pinnedServerSpec,
	};
	await fsp.writeFile(metaPath, JSON.stringify(meta, null, 2) + "\n", "utf8");

	return {
		kind: "pinnedVenv",
		pinnedServerSpec,
		pythonPath,
		pythonVersion: pythonVersionRaw,
		venvPath,
		venvPythonPath,
		scalimCliPath,
		scalimYamlDslLspPath,
		serverPackageVersion,
	};
}

async function resolveSchemaPaths(
	output: vscode.OutputChannel,
	scalimCliPath: string,
): Promise<{ scalimYaml: string; demand: string; workflow: string }> {
	const types = [
		{ key: "scalimYaml", type: "scalim_yaml" },
		{ key: "demand", type: "demand" },
		{ key: "workflow", type: "workflow" },
	] as const;

	const out: Partial<Record<(typeof types)[number]["key"], string>> = {};
	for (const item of types) {
		const result = await runCommand(scalimCliPath, ["yaml-dsl", "schema", "path", "--type", item.type]);
		const schemaPath = result.stdout.trim();
		if (result.exitCode !== 0 || !schemaPath) {
			output.appendLine(`[schema] Failed to resolve schema path type=${item.type} exit=${result.exitCode}`);
			output.appendLine(result.stderr.trim());
			throw new Error("Failed to resolve schema paths");
		}
		if (!path.isAbsolute(schemaPath) || !fs.existsSync(schemaPath)) {
			output.appendLine(`[schema] Resolved path is not an existing absolute path: ${schemaPath}`);
			throw new Error("Invalid schema path from scalim-cli");
		}
		output.appendLine(`[schema] ${item.type}: ${schemaPath}`);
		out[item.key] = schemaPath;
	}

	return {
		scalimYaml: out.scalimYaml ?? "",
		demand: out.demand ?? "",
		workflow: out.workflow ?? "",
	};
}

async function maybeBindSchemas(
	output: vscode.OutputChannel,
	schemaPaths: { scalimYaml: string; demand: string; workflow: string },
): Promise<void> {
	const yamlExt = vscode.extensions.getExtension("redhat.vscode-yaml");
	if (!yamlExt) {
		output.appendLine("[schema] redhat.vscode-yaml not installed; skipping yaml.schemas binding.");
		void vscode.window.showInformationMessage("Scalim YAML DSL: install redhat.vscode-yaml to enable schema support.");
		return;
	}

	const config = vscode.workspace.getConfiguration();
	const existing = config.get<unknown>("yaml.schemas");
	const merged = mergeYamlSchemas(existing, {
		[schemaPaths.scalimYaml]: ["scalim.yaml"],
		[schemaPaths.demand]: ["demand/**/*.y*ml"],
		[schemaPaths.workflow]: ["workflow/**/*.y*ml"],
	});

	await config.update("yaml.schemas", merged, vscode.ConfigurationTarget.Workspace);
	output.appendLine("[schema] Updated workspace yaml.schemas (idempotent merge).");
}

async function maybeBindSchemaForDocument(
	output: vscode.OutputChannel,
	schemaPaths: { scalimYaml: string; demand: string; workflow: string },
	document: vscode.TextDocument,
	schemaRequiredKeys?: { demand: readonly string[]; workflow: readonly string[] },
): Promise<void> {
	if (document.uri.scheme !== "file") {
		return;
	}

	const yamlExt = vscode.extensions.getExtension("redhat.vscode-yaml");
	if (!yamlExt) {
		return;
	}

	const preview = documentPreviewText(document);
	const kind = guessYamlDslKindFromText(preview, schemaRequiredKeys);
	const schemaPath = kind === "workflow" ? schemaPaths.workflow : schemaPaths.demand;

	const workspaceRoot = resolveWorkspaceRoot();
	let matcher = document.uri.fsPath;
	if (workspaceRoot) {
		const rel = path.relative(workspaceRoot, document.uri.fsPath);
		if (rel && !rel.startsWith("..") && !path.isAbsolute(rel)) {
			matcher = rel;
		}
	}
	matcher = matcher.split(path.sep).join("/");

	const config = vscode.workspace.getConfiguration();
	const existing = config.get<unknown>("yaml.schemas");
	const merged = mergeYamlSchemas(existing, {
		[schemaPath]: [matcher],
	});

	await config.update("yaml.schemas", merged, vscode.ConfigurationTarget.Workspace);
	output.appendLine(`[schema] Bound ${kind} schema to ${matcher}`);
}

const schemaRequiredKeysCache = new Map<string, string[]>();

async function readSchemaRequiredKeys(
	output: vscode.OutputChannel,
	schemaPath: string,
): Promise<string[] | undefined> {
	const cached = schemaRequiredKeysCache.get(schemaPath);
	if (cached) {
		return cached;
	}

	try {
		const raw = await fsp.readFile(schemaPath, "utf8");
		const payload = JSON.parse(raw) as unknown;
		if (typeof payload !== "object" || payload === null) {
			return undefined;
		}
		const required = (payload as Record<string, unknown>)["required"];
		if (!Array.isArray(required)) {
			return undefined;
		}
		const keys = required.filter((item): item is string => typeof item === "string").map((key) => key.trim()).filter(Boolean);
		schemaRequiredKeysCache.set(schemaPath, keys);
		return keys;
	} catch (e) {
		output.appendLine(`[schema] Failed to read required keys from schema: ${schemaPath}`);
		output.appendLine(String(e));
		return undefined;
	}
}

async function resolveSchemaRequiredKeys(
	output: vscode.OutputChannel,
	schemaPaths: { demand: string; workflow: string },
): Promise<{ demand: string[]; workflow: string[] } | undefined> {
	const demand = await readSchemaRequiredKeys(output, schemaPaths.demand);
	const workflow = await readSchemaRequiredKeys(output, schemaPaths.workflow);
	if (!demand || !workflow) {
		return undefined;
	}
	return { demand, workflow };
}

async function dumpDiscovery(
	output: vscode.OutputChannel,
	env: ProvisionedEnv,
): Promise<unknown | undefined> {
	const editor = vscode.window.activeTextEditor;
	if (!editor) {
		output.appendLine("[diag] No active editor. Open a YAML file to dump discovery.");
		return undefined;
	}
	if (editor.document.uri.scheme !== "file") {
		output.appendLine(`[diag] Active document is not a file: ${editor.document.uri.toString()}`);
		return undefined;
	}

	const yamlPath = editor.document.uri.fsPath;
	const result = await runCommand(env.scalimYamlDslLspPath, ["dump-discovery", yamlPath, "--json"]);
	if (result.exitCode !== 0) {
		output.appendLine(`[diag] dump-discovery failed (exit=${result.exitCode}).`);
		output.appendLine(result.stderr.trim());
		return undefined;
	}
	try {
		const payload = JSON.parse(result.stdout) as unknown;
		if (typeof payload === "object" && payload !== null) {
			const projectRoot = (payload as Record<string, unknown>)["project_root"];
			if (typeof projectRoot === "string" && projectRoot.trim()) {
				lastProjectRoot = projectRoot.trim();
			}
		}
		output.appendLine(`[diag] dump-discovery(${yamlPath}) = ${JSON.stringify(payload, null, 2)}`);
		return payload;
	} catch (e) {
		output.appendLine("[diag] dump-discovery returned non-JSON payload.");
		output.appendLine(result.stdout.trim());
		return undefined;
	}
}

async function dumpDiscoveryFromServer(
	output: vscode.OutputChannel,
	documentUri: string,
): Promise<unknown | undefined> {
	try {
		const payload = (await vscode.commands.executeCommand("scalim.dumpDiscovery", documentUri)) as unknown;
		if (typeof payload === "object" && payload !== null) {
			const projectRoot = (payload as Record<string, unknown>)["project_root"];
			if (typeof projectRoot === "string" && projectRoot.trim()) {
				lastProjectRoot = projectRoot.trim();
			}
		}
		output.appendLine(`[diag] lsp dumpDiscovery(${documentUri}) = ${JSON.stringify(payload, null, 2)}`);
		return payload;
	} catch (e) {
		output.appendLine("[diag] lsp dumpDiscovery failed.");
		output.appendLine(String(e));
		return undefined;
	}
}

async function stopClient(output: vscode.OutputChannel): Promise<void> {
	if (!currentClient) {
		return;
	}
	expectedStop = true;
	try {
		await currentClient.stop();
	} finally {
		currentClient = undefined;
		expectedStop = false;
		output.appendLine("[lsp] Client stopped.");
	}
}

async function startClient(
	context: vscode.ExtensionContext,
	output: vscode.OutputChannel,
	env: ProvisionedEnv,
): Promise<void> {
	await stopClient(output);

	setStatusBarState(context, "starting", env);

	const serverOptions: ServerOptions = {
		command: env.scalimYamlDslLspPath,
		args: ["serve"],
		options: {
			cwd: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,
		},
	};

	const clientOptions: LanguageClientOptions = {
		documentSelector: [
			{ language: "yaml", scheme: "file" },
			{ language: "yaml", scheme: "untitled" },
		],
		outputChannel: output,
		middleware: {
			provideCodeActions: async (document, range, codeActionContext, token, next) => {
				const items = await Promise.resolve(next(document, range, codeActionContext, token));
				if (!items) {
					return items;
				}

				const quickFixKind = vscode.CodeActionKind.QuickFix.append("scalim");
				return items.map((item) => {
					if (item instanceof vscode.CodeAction) {
						const commandId = item.command?.command;
						item.title = friendlyActionTitle(item.title, commandId);
						if (isScalimCommandId(commandId)) {
							item.kind = quickFixKind;
						}
						return item;
					}

					const commandId = item.command;
					const action = new vscode.CodeAction(friendlyActionTitle(item.title, commandId), quickFixKind);
					action.command = item;
					return action;
				});
			},
			executeCommand: async (command, args, next) => {
				output.appendLine(`[lsp] executeCommand: ${command} args=${summarizeArgs(args)}`);
				try {
					const result = await Promise.resolve(next(command, args));
					output.appendLine(`[lsp] executeCommand ok: ${command}`);
					if (command.startsWith("scalim.yaml.")) {
						void dumpDiscovery(output, env);
					}
					return result;
				} catch (e) {
					output.appendLine(`[lsp] executeCommand failed: ${command}`);
					output.appendLine(String(e));
					void vscode.window
						.showErrorMessage(
							`Scalim YAML DSL: executeCommand failed: ${command}`,
							"Open logs",
							"Restart server",
							"Reinstall server",
						)
						.then((choice) => {
							if (choice === "Open logs") {
								output.show(true);
							}
								if (choice === "Restart server") {
									void restartServer(context, output, /*reinstall*/ false, /*allowInstall*/ false);
								}
								if (choice === "Reinstall server") {
									void restartServer(context, output, /*reinstall*/ true, /*allowInstall*/ true);
								}
							});
					return undefined;
				}
			},
		},
	};

	const client = new LanguageClient("scalimYamlDsl", "Scalim YAML DSL", serverOptions, clientOptions);
	currentClient = client;

	context.subscriptions.push(
		client.onDidChangeState((event) => {
			if (event.newState === State.Running) {
				setStatusBarState(context, "running", env);
			}
			if (event.newState === State.Stopped) {
				setStatusBarState(context, "stopped", env);
			}
			if (event.newState === State.Stopped && !expectedStop) {
				output.appendLine("[lsp] Server stopped unexpectedly. Use 'Scalim YAML DSL: Restart server' to recover.");
				void vscode.window.showErrorMessage(
					"Scalim YAML DSL server stopped unexpectedly.",
					"Open logs",
					"Restart server",
					"Reinstall server",
				).then((choice) => {
					if (choice === "Open logs") {
						output.show(true);
					}
						if (choice === "Restart server") {
							void restartServer(context, output, /*reinstall*/ false, /*allowInstall*/ false);
						}
						if (choice === "Reinstall server") {
							void restartServer(context, output, /*reinstall*/ true, /*allowInstall*/ true);
						}
					});
			}
		}),
	);

	output.appendLine(`[lsp] Starting: ${env.scalimYamlDslLspPath} serve`);
	try {
		await client.start();
		output.appendLine("[lsp] Ready.");
		setStatusBarState(context, "running", env);
	} catch (e) {
		lastStartError = String(e);
		output.appendLine("[lsp] Failed to start.");
		output.appendLine(String(e));
		setStatusBarState(context, "stopped", env);
		void vscode.window.showErrorMessage(
			"Scalim YAML DSL: failed to start server.",
			"Open logs",
			"Reinstall server",
		).then((choice) => {
			if (choice === "Open logs") {
				output.show(true);
			}
				if (choice === "Reinstall server") {
					void restartServer(context, output, /*reinstall*/ true, /*allowInstall*/ true);
				}
			});
	}
}

async function restartServer(
	context: vscode.ExtensionContext,
	output: vscode.OutputChannel,
	reinstall: boolean,
	allowInstall: boolean,
): Promise<void> {
	const run = async (): Promise<void> => {
		const { envMode, workspaceVenvPath, pythonPathOverride, pinnedServerSpec, autoSchemaBinding } = getExtensionConfig();
		lastStartError = undefined;
		setStatusBarState(context, "starting", currentEnv);

		try {
			if (reinstall) {
				output.appendLine("[cmd] Reinstall server requested (rebuild venv).");
				currentEnv = undefined;
				try {
					const storagePath = context.globalStorageUri.fsPath;
					const venvPath = path.join(storagePath, "scalim-yaml-dsl-lsp-venv");
					await fsp.rm(venvPath, { recursive: true, force: true });
				} catch (e) {
					output.appendLine(`[cmd] Failed to remove venv: ${String(e)}`);
				}
			}

			const workspaceRoot = resolveWorkspaceRoot();
			let env: ProvisionedEnv | undefined;

			if (envMode === "workspaceVenv" && !workspaceRoot) {
				setStatusBarState(context, "stopped", currentEnv);
				void vscode.window.showErrorMessage("Scalim YAML DSL: no workspace folder is open (required for envMode=workspaceVenv).", "Open logs").then((choice) => {
					if (choice === "Open logs") {
						output.show(true);
					}
				});
				return;
			}

			if ((envMode === "workspaceVenv" || envMode === "auto") && workspaceRoot) {
				env = await resolveWorkspaceVenvEnv(output, workspaceRoot, workspaceVenvPath);
				if (!env) {
					if (envMode === "workspaceVenv") {
						setStatusBarState(context, "stopped", currentEnv);
						void vscode.window.showErrorMessage(
							"Scalim YAML DSL: workspace venv is not usable. Configure scalim.yamlDsl.workspaceVenvPath or switch envMode.",
							"Open logs",
						).then((choice) => {
							if (choice === "Open logs") {
								output.show(true);
							}
						});
						return;
					}
					output.appendLine("[workspace] envMode=auto but workspace venv not usable; trying PATH next.");
				}
			}

			if (!env && envMode === "auto") {
				env = await resolvePathEnv(output);
			}

			if (!env && envMode === "pinnedVenv") {
				const py = await detectPython(output, pythonPathOverride);
				if (!py) {
					setStatusBarState(context, "stopped", currentEnv);
					void vscode.window.showErrorMessage(
						"Scalim YAML DSL requires Python >=3.10. Configure scalim.yamlDsl.pythonPath or install python3.",
						"Open logs",
					).then((choice) => {
						if (choice === "Open logs") {
							output.show(true);
						}
					});
					output.appendLine("[python] No suitable python found.");
					return;
				}

				env = await ensureVenv(context, output, py.pythonPath, pinnedServerSpec, allowInstall);
			}

			if (!env) {
				setStatusBarState(context, "stopped", currentEnv);

				const installCmd = `uv tool install "${pinnedServerSpec}"`;
				output.appendLine("[env] No usable server environment found.");
				output.appendLine(`[env] Install (recommended): ${installCmd}`);

				void vscode.window
					.showErrorMessage(
						"Scalim YAML DSL: LSP server not found. Install it first (recommended: uv tool).",
						"Open terminal",
						"Copy install command",
						"Open logs",
					)
					.then(async (choice) => {
						if (choice === "Open logs") {
							output.show(true);
							return;
						}
						if (choice === "Copy install command") {
							await vscode.env.clipboard.writeText(installCmd);
							void vscode.window.showInformationMessage("Scalim YAML DSL: install command copied to clipboard.");
							return;
						}
						if (choice === "Open terminal") {
							const term = vscode.window.createTerminal("Scalim YAML DSL");
							term.show(true);
							term.sendText(installCmd, false);
						}
					});
				return;
			}

			currentEnv = env;

			try {
				const schemaPaths = await resolveSchemaPaths(output, env.scalimCliPath);
				env.schemaPaths = schemaPaths;
				env.schemaRequiredKeys = await resolveSchemaRequiredKeys(output, {
					demand: schemaPaths.demand,
					workflow: schemaPaths.workflow,
				});

				if (autoSchemaBinding) {
					await maybeBindSchemas(output, schemaPaths);
				} else {
					output.appendLine("[schema] autoSchemaBinding=false; skipping workspace yaml.schemas update.");
				}
			} catch (e) {
				output.appendLine(`[schema] Skipping schema binding. err=${String(e)}`);
			}

			await startClient(context, output, env);
		} catch (e) {
			lastStartError = String(e);
			output.appendLine("[error] Failed to provision/start Scalim YAML DSL.");
			output.appendLine(lastStartError);
			setStatusBarState(context, "stopped", currentEnv);
			void vscode.window
				.showErrorMessage("Scalim YAML DSL: provisioning failed.", "Open logs", "Reinstall server")
				.then((choice) => {
					if (choice === "Open logs") {
						output.show(true);
					}
						if (choice === "Reinstall server") {
							void restartServer(context, output, /*reinstall*/ true, /*allowInstall*/ true);
						}
					});
		}
	};

	if (startMutex) {
		output.appendLine("[mutex] Restart already in progress; waiting...");
		await startMutex;
		return;
	}
	startMutex = run().finally(() => {
		startMutex = undefined;
	});
	await startMutex;
}

async function ensureProvisionedEnv(
	context: vscode.ExtensionContext,
	output: vscode.OutputChannel,
): Promise<ProvisionedEnv | undefined> {
	if (currentEnv) {
		return currentEnv;
	}
	output.appendLine("[env] No provisioned environment yet; provisioning first.");
	await restartServer(context, output, /*reinstall*/ false, /*allowInstall*/ false);
	return currentEnv;
}

function getDiscoveryString(payload: unknown, key: string): string | undefined {
	if (typeof payload !== "object" || payload === null) {
		return undefined;
	}
	const value = (payload as Record<string, unknown>)[key];
	if (typeof value === "string" && value.trim()) {
		return value.trim();
	}
	return undefined;
}

async function openOrCreateScalimYaml(context: vscode.ExtensionContext, output: vscode.OutputChannel): Promise<void> {
	const _env = await ensureProvisionedEnv(context, output);
	if (!_env) {
		return;
	}

	const editor = vscode.window.activeTextEditor;
	if (!editor || editor.document.uri.scheme !== "file") {
		void vscode.window.showInformationMessage("Scalim YAML DSL: open a YAML file first to create scalim.yaml via Quick Fix.");
		return;
	}

	const documentUri = editor.document.uri.toString();
	const payload = await dumpDiscoveryFromServer(output, documentUri);
	const scalimYamlPath = getDiscoveryString(payload, "scalim_yaml_path");
	if (scalimYamlPath) {
		const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(scalimYamlPath));
		await vscode.window.showTextDocument(doc);
		return;
	}

	const projectRoot = getDiscoveryString(payload, "project_root") ?? vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
	if (!projectRoot) {
		void vscode.window.showErrorMessage("Scalim YAML DSL: no workspace folder is open.");
		return;
	}

	output.appendLine("[cmd] scalim.yaml missing; executing server command scalim.yaml.createMinimal");
	try {
		await vscode.commands.executeCommand("scalim.yaml.createMinimal", documentUri);
	} catch (e) {
		output.appendLine("[cmd] Failed to execute scalim.yaml.createMinimal");
		output.appendLine(String(e));
		void vscode.window.showErrorMessage("Scalim YAML DSL: failed to create scalim.yaml (see logs).", "Open logs").then((choice) => {
			if (choice === "Open logs") {
				output.show(true);
			}
		});
		return;
	}

	const payloadAfter = await dumpDiscoveryFromServer(output, documentUri);
	const scalimYamlPathAfter = getDiscoveryString(payloadAfter, "scalim_yaml_path");
	if (scalimYamlPathAfter) {
		const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(scalimYamlPathAfter));
		await vscode.window.showTextDocument(doc);
		return;
	}

	const createdPath = path.join(projectRoot, "scalim.yaml");
	const createdUri = vscode.Uri.file(createdPath);
	try {
		await vscode.workspace.fs.stat(createdUri);
	} catch {
		output.appendLine(`[cmd] scalim.yaml not found at expected path after create: ${createdPath}`);
		void vscode.window.showWarningMessage("Scalim YAML DSL: scalim.yaml created, but could not locate it at expected path. See logs.");
		return;
	}

	const doc = await vscode.workspace.openTextDocument(createdUri);
	await vscode.window.showTextDocument(doc);
}

function clientState(): State | undefined {
	return currentClient?.state;
}

function clientIsRunningOrStarting(): boolean {
	const state = clientState();
	return state === State.Running || state === State.Starting;
}

async function maybeAutostartForDocument(
	context: vscode.ExtensionContext,
	output: vscode.OutputChannel,
	document: vscode.TextDocument | undefined,
): Promise<void> {
	if (!document) {
		return;
	}
	if (!isLikelyScalimYamlDslDocument(document)) {
		return;
	}

	// Even when the LSP is already running, bind schema for files outside conventional globs.
	const cfg = getExtensionConfig();
	if (cfg.autoSchemaBinding && currentEnv?.schemaPaths) {
		void maybeBindSchemaForDocument(output, currentEnv.schemaPaths, document, currentEnv.schemaRequiredKeys);
	}

	if (clientIsRunningOrStarting() || startMutex) {
		return;
	}
	if (autoStartAttempted && !currentClient) {
		return;
	}

	autoStartAttempted = true;
	output.appendLine(`[auto] Detected Scalim YAML DSL document: ${document.uri.toString()}`);
	await restartServer(context, output, /*reinstall*/ false, /*allowInstall*/ false);

	if (cfg.autoSchemaBinding && currentEnv?.schemaPaths) {
		await maybeBindSchemaForDocument(output, currentEnv.schemaPaths, document, currentEnv.schemaRequiredKeys);
	}
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
	const output = vscode.window.createOutputChannel("Scalim YAML DSL");
	context.subscriptions.push(output);

	output.appendLine("[activate] Scalim YAML DSL extension activated.");
	lastProjectRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? lastProjectRoot;
	setStatusBarState(context, "stopped", currentEnv);

	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.restartServer", async () => {
			await restartServer(context, output, /*reinstall*/ false, /*allowInstall*/ false);
		}),
	);
	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.reinstallServer", async () => {
			await restartServer(context, output, /*reinstall*/ true, /*allowInstall*/ true);
		}),
	);
	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.showDiagnostics", async () => {
			const env = await ensureProvisionedEnv(context, output);
			if (!env) {
				return;
			}
			output.appendLine(
				[
					"[diag] Environment:",
					`  envKind=${env.kind}`,
					`  venvPath=${env.venvPath}`,
					`  pythonPath=${env.pythonPath}`,
					`  pythonVersion=${env.pythonVersion}`,
					`  serverVersion=${env.serverPackageVersion ?? "<unknown>"}`,
					`  pinnedServerSpec=${env.pinnedServerSpec}`,
					lastStartError ? `  lastStartError=${lastStartError}` : undefined,
					lastProjectRoot ? `  lastProjectRoot=${lastProjectRoot}` : undefined,
				].join("\n"),
			);
			if (env.schemaPaths) {
				output.appendLine(`[diag] schemaPaths=${JSON.stringify(env.schemaPaths, null, 2)}`);
			}
			await dumpDiscovery(output, env);
			output.show(true);
		}),
	);

	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.openLogs", async () => {
			output.show(true);
		}),
	);

	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.showDiscoverySummary", async () => {
			const env = await ensureProvisionedEnv(context, output);
			if (!env) {
				return;
			}
			await dumpDiscovery(output, env);
			output.show(true);
		}),
	);

	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.openOrCreateScalimYaml", async () => {
			await openOrCreateScalimYaml(context, output);
		}),
	);

	context.subscriptions.push(
		vscode.window.onDidChangeActiveTextEditor((editor) => {
			void maybeAutostartForDocument(context, output, editor?.document);
		}),
	);
	context.subscriptions.push(
		vscode.workspace.onDidOpenTextDocument((document) => {
			void maybeAutostartForDocument(context, output, document);
		}),
	);
	context.subscriptions.push(
		vscode.workspace.onDidChangeTextDocument((event) => {
			void maybeAutostartForDocument(context, output, event.document);
		}),
	);

	// Best-effort auto-start: only trigger when the workspace actually contains a likely YAML DSL document.
	void maybeAutostartForDocument(context, output, vscode.window.activeTextEditor?.document);
	for (const document of vscode.workspace.textDocuments) {
		void maybeAutostartForDocument(context, output, document);
	}
}

export async function deactivate(): Promise<void> {
	if (currentClient) {
		expectedStop = true;
		try {
			await currentClient.stop();
		} finally {
			currentClient = undefined;
			expectedStop = false;
		}
	}
}
