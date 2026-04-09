import * as fs from "node:fs";
import * as fsp from "node:fs/promises";
import * as path from "node:path";

import * as vscode from "vscode";
import {
	LanguageClient,
	type LanguageClientOptions,
	type ServerOptions,
	State,
	Trace,
} from "vscode-languageclient/node";

import { runCommand } from "./internal/exec";
import {
	extractPinnedVersion,
	renderDiagnosticBundle,
	summarizeDiscoveryPayload,
	type DiscoverySummary,
} from "./internal/diagnosticBundle";
import { mergeYamlSchemas } from "./internal/yamlSchemas";

const DEFAULT_PINNED_SERVER_SPEC = "scalim-yaml-dsl-lsp[server]";
const DEFAULT_ENV_MODE = "auto";
const DEFAULT_WORKSPACE_VENV_PATH = ".venv";
const DEFAULT_AUTO_RESTART_ON_SCALIM_YAML_CHANGE = false;

const PRESET_VDOC_SCHEME = "scalim-preset";

type EnvMode = "pinnedVenv" | "workspaceVenv" | "auto" | "path";

type ActiveDocumentKind = "demand" | "workflow" | "config";

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
const expectedStoppedClients = new WeakSet<LanguageClient>();
let startMutex: Promise<void> | undefined;
let statusBarItem: vscode.StatusBarItem | undefined;
let lastStartError: string | undefined;
let lastProjectRoot: string | undefined;
let lastScalimYamlPath: string | undefined;
let lastDiscovery: DiscoverySummary | undefined;
let lastResolutionTrace: unknown | undefined;
let extensionLogPath: string | undefined;
let serverLogPath: string | undefined;
let autoStartAttempted = false;
let lastActiveDocumentKind: ActiveDocumentKind | undefined;

type LogLevel = "DEBUG" | "INFO" | "WARN" | "ERROR";
type ServerLogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR";
type LspTraceLevel = "off" | "messages" | "verbose";

const LOG_LEVEL_ORDER: Readonly<Record<LogLevel, number>> = Object.freeze({
	DEBUG: 10,
	INFO: 20,
	WARN: 30,
	ERROR: 40,
});

let extensionLogThreshold: LogLevel = "INFO";
let lspTraceOutputChannel: vscode.OutputChannel | undefined;

function getNowIso(): string {
	return new Date().toISOString();
}

async function appendLogLineToFile(filePath: string, text: string): Promise<void> {
	try {
		await fsp.mkdir(path.dirname(filePath), { recursive: true });
		await fsp.appendFile(filePath, text + "\n", "utf8");
	} catch {
		// Best-effort; never block core UX on logging.
	}
}

function log(level: LogLevel, message: string): void {
	if (!outputChannelForLogs) {
		return;
	}
	if (LOG_LEVEL_ORDER[level] < LOG_LEVEL_ORDER[extensionLogThreshold]) {
		return;
	}
	const ts = getNowIso();
	const prefix = `${ts} ${level} `;
	const raw = String(message ?? "");
	const lines = raw.split(/\r?\n/);
	const formatted = lines.map((line) => prefix + line);
	for (const line of formatted) {
		outputChannelForLogs.appendLine(line);
	}
	if (extensionLogPath) {
		void appendLogLineToFile(extensionLogPath, formatted.join("\n"));
	}
}

function logDebug(message: string): void {
	log("DEBUG", message);
}

function logInfo(message: string): void {
	log("INFO", message);
}

function logWarn(message: string): void {
	log("WARN", message);
}

function logError(message: string): void {
	log("ERROR", message);
}

let outputChannelForLogs: vscode.OutputChannel | undefined;

function ensureLspTraceOutputChannel(context: vscode.ExtensionContext): vscode.OutputChannel {
	if (lspTraceOutputChannel) {
		return lspTraceOutputChannel;
	}
	const channel = vscode.window.createOutputChannel("Scalim YAML DSL (LSP Trace)");
	context.subscriptions.push(channel);
	lspTraceOutputChannel = channel;
	return channel;
}

function parseExtensionLogThreshold(raw: string | undefined): LogLevel {
	const normalized = (raw || "").trim().toLowerCase();
	if (normalized === "debug") {
		return "DEBUG";
	}
	if (normalized === "warn" || normalized === "warning") {
		return "WARN";
	}
	if (normalized === "error") {
		return "ERROR";
	}
	return "INFO";
}

function parseServerLogLevel(raw: string | undefined): ServerLogLevel {
	const normalized = (raw || "").trim().toLowerCase();
	if (normalized === "debug") {
		return "DEBUG";
	}
	if (normalized === "warning" || normalized === "warn") {
		return "WARNING";
	}
	if (normalized === "error") {
		return "ERROR";
	}
	return "INFO";
}

function parseLspTraceLevel(raw: string | undefined): LspTraceLevel {
	const normalized = (raw || "").trim().toLowerCase();
	if (normalized === "messages") {
		return "messages";
	}
	if (normalized === "verbose") {
		return "verbose";
	}
	return "off";
}

function lspTraceLevelToProtocolTrace(level: LspTraceLevel): Trace {
	if (level === "messages") {
		return Trace.Messages;
	}
	if (level === "verbose") {
		return Trace.Verbose;
	}
	return Trace.Off;
}

function parsePackageVersionFromShowOutput(stdout: string): string | undefined {
	return (
		stdout
			.split(/\r?\n/g)
			.map((line) => line.trim())
			.find((line) => line.toLowerCase().startsWith("version:"))
			?.split(":", 2)[1]
			?.trim() || undefined
	);
}

async function probePythonPackageVersion(
	pythonPath: string,
	packageName: string,
	options: { cwd: string },
): Promise<string | undefined> {
	const { cwd } = options;
	// 1) uv (works even when venv has no pip)
	const uvResult = await runCommand("uv", ["pip", "show", "--python", pythonPath, packageName], { cwd });
	const uvVersion = parsePackageVersionFromShowOutput(uvResult.stdout);
	if (uvResult.exitCode === 0 && uvVersion) {
		return uvVersion;
	}

	// 2) stdlib importlib.metadata
	const pyCode = [
		"import sys",
		"try:",
		" import importlib.metadata as m",
		"except Exception:",
		" import importlib_metadata as m",
		"try:",
		` print(m.version(${JSON.stringify(packageName)}))`,
		"except Exception:",
		" sys.exit(1)",
	].join("\n");
	const metaResult = await runCommand(pythonPath, ["-c", pyCode], { cwd });
	const metaVersion = (metaResult.stdout || metaResult.stderr).trim();
	if (metaResult.exitCode === 0 && metaVersion) {
		return metaVersion;
	}

	// 3) fallback: python -m pip show
	const pipResult = await runCommand(pythonPath, ["-m", "pip", "show", packageName], { cwd });
	const pipVersion = parsePackageVersionFromShowOutput(pipResult.stdout);
	if (pipResult.exitCode === 0 && pipVersion) {
		return pipVersion;
	}

	return undefined;
}

async function initializeLogFiles(context: vscode.ExtensionContext): Promise<void> {
	const storagePath = context.globalStorageUri.fsPath;
	extensionLogPath = path.join(storagePath, "extension.log");
	serverLogPath = path.join(storagePath, "server.log");
	try {
		await fsp.mkdir(storagePath, { recursive: true });
		if (!fs.existsSync(extensionLogPath)) {
			await fsp.writeFile(extensionLogPath, "", "utf8");
		}
		if (!fs.existsSync(serverLogPath)) {
			await fsp.writeFile(serverLogPath, "", "utf8");
		}
	} catch {
		// ignore
	}
}

function ensureStatusBar(context: vscode.ExtensionContext): vscode.StatusBarItem {
	if (statusBarItem) {
		return statusBarItem;
	}

	const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
	item.command = "scalim.yamlDsl.openStatusMenu";
	item.text = "Scalim";
	item.tooltip = "Scalim";
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

	const kindLabel = lastActiveDocumentKind ? ` ${lastActiveDocumentKind}` : "";
	const projectRoot = lastProjectRoot ?? "<unknown>";
	const projectRootBase = projectRoot !== "<unknown>" ? path.basename(projectRoot) : "";
	const scalimYamlPath = lastScalimYamlPath ?? "<missing>";
	const discoveryLabel = scalimYamlPath !== "<missing>" ? projectRootBase : "No scalim.yaml";

	if (status === "starting") {
		item.text = `$(sync~spin) Scalim${kindLabel}`;
	} else if (status === "running") {
		item.text = `$(check) Scalim${kindLabel}${discoveryLabel ? ` · ${discoveryLabel}` : ""}`;
	} else {
		item.text = `$(error) Scalim${kindLabel}${discoveryLabel ? ` · ${discoveryLabel}` : ""}`;
	}

	const tooltip = [
		"Scalim",
		`status=${status}`,
		`activeDocKind=${lastActiveDocumentKind ?? "<none>"}`,
		`serverVersion=${env?.serverPackageVersion ?? "<unknown>"}`,
		`projectRoot=${projectRoot}`,
		`scalimYamlPath=${scalimYamlPath}`,
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
	autoRestartOnScalimYamlChange: boolean;
	serverDebounceMs: number;
	autoRestartOnSettingsChange: boolean;
	logLevel: LogLevel;
	serverLogLevel: ServerLogLevel;
	lspTrace: LspTraceLevel;
} {
	const cfg = vscode.workspace.getConfiguration("scalim.yamlDsl");
	const envModeRaw = (cfg.get<string>("envMode") || "").trim() || DEFAULT_ENV_MODE;
	const envMode: EnvMode =
		envModeRaw === "workspaceVenv" || envModeRaw === "auto" || envModeRaw === "pinnedVenv" || envModeRaw === "path"
			? envModeRaw
			: "pinnedVenv";
	const workspaceVenvPath = (cfg.get<string>("workspaceVenvPath") || "").trim() || DEFAULT_WORKSPACE_VENV_PATH;
	const pythonPathOverride = (cfg.get<string>("pythonPath") || "").trim() || undefined;
	const pinnedServerSpec = (cfg.get<string>("pinnedServerSpec") || "").trim() || DEFAULT_PINNED_SERVER_SPEC;
	const autoSchemaBinding = cfg.get<boolean>("autoSchemaBinding", true);
	const autoRestartOnScalimYamlChange = cfg.get<boolean>(
		"autoRestartOnScalimYamlChange",
		DEFAULT_AUTO_RESTART_ON_SCALIM_YAML_CHANGE,
	);
	const serverDebounceMs = cfg.get<number>("serverDebounceMs", 200);
	const autoRestartOnSettingsChange = cfg.get<boolean>("autoRestartOnSettingsChange", false);
	const logLevel = parseExtensionLogThreshold(cfg.get<string>("logLevel"));
	const serverLogLevel = parseServerLogLevel(cfg.get<string>("serverLogLevel"));
	const lspTrace = parseLspTraceLevel(cfg.get<string>("lspTrace"));
	return {
		envMode,
		workspaceVenvPath,
		pythonPathOverride,
		pinnedServerSpec,
		autoSchemaBinding,
		autoRestartOnScalimYamlChange,
		serverDebounceMs,
		autoRestartOnSettingsChange,
		logLevel,
		serverLogLevel,
		lspTrace,
	};
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

	logInfo(`[python] Detecting python (>=3.10). Candidates: ${candidates.join(", ")}`);

	for (const candidate of candidates) {
		const result = await runCommand(candidate, ["-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"]);
		const combined = (result.stdout || result.stderr).trim();
		const semver = parseSemver(combined);
		if (!semver) {
			logWarn(`[python] ${candidate}: unable to parse version from: ${JSON.stringify(combined)}`);
			continue;
		}
		logInfo(`[python] ${candidate}: ${semver.major}.${semver.minor}.${semver.patch}`);
		if (!satisfiesPython310(semver)) {
			logWarn(`[python] ${candidate}: version too old (need >=3.10)`);
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
	if (document.uri.scheme === PRESET_VDOC_SCHEME) {
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

function detectActiveDocumentKind(
	document: vscode.TextDocument,
	schemaRequiredKeys?: { demand: readonly string[]; workflow: readonly string[] },
): ActiveDocumentKind | undefined {
	if (document.languageId !== "yaml") {
		return undefined;
	}
	if (document.uri.scheme === "file" && path.basename(document.uri.fsPath) === "scalim.yaml") {
		return "config";
	}
	if (!isLikelyScalimYamlDslDocument(document)) {
		return undefined;
	}
	const preview = documentPreviewText(document);
	return guessYamlDslKindFromText(preview, schemaRequiredKeys);
}

function currentStatusBarState(): "starting" | "running" | "stopped" {
	const state = clientState();
	if (state === State.Running) {
		return "running";
	}
	if (state === State.Starting || startMutex) {
		return "starting";
	}
	return "stopped";
}

function updateActiveDocumentKindAndRefreshStatusBar(context: vscode.ExtensionContext, document: vscode.TextDocument): void {
	const nextKind = detectActiveDocumentKind(document, currentEnv?.schemaRequiredKeys);
	if (nextKind === lastActiveDocumentKind) {
		return;
	}
	lastActiveDocumentKind = nextKind;
	setStatusBarState(context, currentStatusBarState(), currentEnv);
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
		logWarn("[path] scalim-yaml-dsl-lsp not found in PATH.");
		return undefined;
	}

	const scalimCliPath = "scalim-cli";
	const cliHelp = await runCommand(scalimCliPath, ["--help"]);
	if (cliHelp.exitCode !== 0) {
		logWarn("[path] scalim-cli not found in PATH; schema binding will be skipped.");
	}

	logInfo(`[path] Using PATH commands: ${scalimYamlDslLspPath} / ${scalimCliPath}`);

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
		logWarn(`[workspace] workspaceVenvPath not found: ${venvPath}`);
		return undefined;
	}

	const venvPythonPath =
		findVenvExecutable(venvPath, "python") ??
		findVenvExecutable(venvPath, "python3") ??
		path.join(getVenvScriptsDir(venvPath), isWindows() ? "python.exe" : "python");
	if (!fs.existsSync(venvPythonPath)) {
		logWarn(`[workspace] Missing python in workspace venv: ${venvPythonPath}`);
		return undefined;
	}

	const pythonVersionResult = await runCommand(venvPythonPath, ["-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"]);
	const pythonVersionRaw = (pythonVersionResult.stdout || pythonVersionResult.stderr).trim();
	const pythonVersion = parseSemver(pythonVersionRaw);
	if (!pythonVersion) {
		logWarn(`[workspace] Unable to parse python version from: ${JSON.stringify(pythonVersionRaw)}`);
		return undefined;
	}
	if (!satisfiesPython310(pythonVersion)) {
		logWarn(`[workspace] Python version too old (need >=3.10): ${pythonVersion.major}.${pythonVersion.minor}.${pythonVersion.patch}`);
		return undefined;
	}

	const scalimCliPath = findVenvExecutable(venvPath, "scalim-cli");
	const scalimYamlDslLspPath = findVenvExecutable(venvPath, "scalim-yaml-dsl-lsp");
	if (!scalimCliPath || !scalimYamlDslLspPath) {
		logWarn(`[workspace] Missing expected executables in workspace venv scripts dir: ${getVenvScriptsDir(venvPath)}`);
		logWarn(`[workspace] scalim-cli: ${scalimCliPath ?? "<missing>"}`);
		logWarn(`[workspace] scalim-yaml-dsl-lsp: ${scalimYamlDslLspPath ?? "<missing>"}`);
		return undefined;
	}

	const serverPackageVersion = await probePythonPackageVersion(venvPythonPath, "scalim-yaml-dsl-lsp", { cwd: workspaceRoot });

	logInfo(`[workspace] Using workspace venv: ${venvPath}`);
	logInfo(`[workspace] python=${venvPythonPath} version=${pythonVersionRaw}`);
	logInfo(`[workspace] scalim-cli=${scalimCliPath}`);
	logInfo(`[workspace] scalim-yaml-dsl-lsp=${scalimYamlDslLspPath}`);

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
		logWarn("[venv] pinned venv missing; install is disabled (need explicit user action).");
		throw new Error("Pinned venv is not provisioned");
	}
	if (needCreate) {
		logInfo(`[venv] Creating venv at ${venvPath}`);
		const result = await runCommand(pythonPath, ["-m", "venv", venvPath], { cwd: storagePath });
		if (result.exitCode !== 0) {
			logError(`[venv] Failed to create venv (exit=${result.exitCode})`);
			logError(result.stderr.trim());
			throw new Error("Failed to create venv");
		}
	} else {
		logInfo(`[venv] Reusing venv at ${venvPath}`);
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
			logWarn(`[venv] Failed to read/parse meta; will reinstall pinned server. err=${String(e)}`);
		}
	}

	if (needInstall && !allowInstall) {
		logWarn("[pip] pinned server not installed or meta mismatch; install is disabled (need explicit user action).");
		throw new Error("Pinned server is not provisioned");
	}

	if (needInstall) {
		const installArgs = ["-m", "pip", "install", "--upgrade", pinnedServerSpec];
		logInfo(`[pip] Installing pinned server: ${pinnedServerSpec}`);
		logInfo(`[pip] Command: ${venvPythonPath} ${installArgs.join(" ")}`);
		const installResult = await runCommand(venvPythonPath, installArgs, { cwd: storagePath });
		if (installResult.exitCode !== 0) {
			logError(`[pip] Install failed (exit=${installResult.exitCode})`);
			logError(installResult.stderr.trim());
			throw new Error("Failed to install pinned server");
		}
	} else {
		logInfo(`[pip] Reusing pinned server install: ${pinnedServerSpec}`);
	}

	const serverPackageVersion = await probePythonPackageVersion(venvPythonPath, "scalim-yaml-dsl-lsp", { cwd: storagePath });

	const scalimCliPath = findVenvExecutable(venvPath, "scalim-cli");
	const scalimYamlDslLspPath = findVenvExecutable(venvPath, "scalim-yaml-dsl-lsp");
	if (!scalimCliPath || !scalimYamlDslLspPath) {
		logError(`[venv] Missing expected executables in venv scripts dir: ${getVenvScriptsDir(venvPath)}`);
		logError(`[venv] scalim-cli: ${scalimCliPath ?? "<missing>"}`);
		logError(`[venv] scalim-yaml-dsl-lsp: ${scalimYamlDslLspPath ?? "<missing>"}`);
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
			logError(`[schema] Failed to resolve schema path type=${item.type} exit=${result.exitCode}`);
			logError(result.stderr.trim());
			throw new Error("Failed to resolve schema paths");
		}
		if (!path.isAbsolute(schemaPath) || !fs.existsSync(schemaPath)) {
			logError(`[schema] Resolved path is not an existing absolute path: ${schemaPath}`);
			throw new Error("Invalid schema path from scalim-cli");
		}
		logInfo(`[schema] ${item.type}: ${schemaPath}`);
		out[item.key] = schemaPath;
	}

	return {
		scalimYaml: out.scalimYaml ?? "",
		demand: out.demand ?? "",
		workflow: out.workflow ?? "",
	};
}

type YamlSchemasBindingStatus = {
	bound: boolean;
	missing: string[];
};

function normalizeYamlSchemasPatterns(value: unknown): string[] {
	if (typeof value === "string") {
		return [value];
	}
	if (Array.isArray(value) && value.every((item) => typeof item === "string")) {
		return value.slice();
	}
	return [];
}

function yamlSchemasBindingStatus(existing: unknown, additions: Record<string, string[]>): YamlSchemasBindingStatus {
	const base = typeof existing === "object" && existing !== null && !Array.isArray(existing) ? (existing as Record<string, unknown>) : {};
	const missing: string[] = [];

	for (const [schema, patterns] of Object.entries(additions)) {
		const existingPatterns = normalizeYamlSchemasPatterns(base[schema]);
		for (const pattern of patterns) {
			if (!existingPatterns.includes(pattern)) {
				missing.push(`${schema} -> ${pattern}`);
			}
		}
	}

	return { bound: missing.length === 0, missing };
}

async function applyYamlSchemasBinding(
	schemaPaths: { scalimYaml: string; demand: string; workflow: string },
): Promise<void> {
	const config = vscode.workspace.getConfiguration();
	const existing = config.get<unknown>("yaml.schemas");
	const merged = mergeYamlSchemas(existing, {
		[schemaPaths.scalimYaml]: ["scalim.yaml"],
		[schemaPaths.demand]: ["demand/**/*.y*ml"],
		[schemaPaths.workflow]: ["workflow/**/*.y*ml"],
	});

	await config.update("yaml.schemas", merged, vscode.ConfigurationTarget.Workspace);
	logInfo("[schema] Updated workspace yaml.schemas (idempotent merge).");
}

const WORKSPACE_STATE_SCHEMA_BINDING_NEVER_PROMPT = "scalim.yamlDsl.schemaBindingNeverPrompt";
let schemaBindingPromptedThisSession = false;

async function bindSchemasWithUserConfirmation(
	context: vscode.ExtensionContext,
	schemaPaths: { scalimYaml: string; demand: string; workflow: string },
	options: { reason: string; promptOncePerSession: boolean },
): Promise<boolean> {
	const yamlExt = vscode.extensions.getExtension("redhat.vscode-yaml");
	if (!yamlExt) {
		logWarn("[schema] redhat.vscode-yaml not installed; cannot bind yaml.schemas.");
		void vscode.window.showInformationMessage("Scalim: install redhat.vscode-yaml to enable schema support.");
		return false;
	}

	const config = vscode.workspace.getConfiguration();
	const existing = config.get<unknown>("yaml.schemas");
	const additions = {
		[schemaPaths.scalimYaml]: ["scalim.yaml"],
		[schemaPaths.demand]: ["demand/**/*.y*ml"],
		[schemaPaths.workflow]: ["workflow/**/*.y*ml"],
	};
	const status = yamlSchemasBindingStatus(existing, additions);
	if (status.bound) {
		return true;
	}

	const neverPrompt = context.workspaceState.get<boolean>(WORKSPACE_STATE_SCHEMA_BINDING_NEVER_PROMPT, false);
	if (neverPrompt) {
		return false;
	}
	if (options.promptOncePerSession && schemaBindingPromptedThisSession) {
		return false;
	}
	if (options.promptOncePerSession) {
		schemaBindingPromptedThisSession = true;
	}

	const missing = status.missing.length ? `\n\nMissing:\n- ${status.missing.join("\n- ")}` : "";
	const choice = await vscode.window.showInformationMessage(
		`Scalim: yaml.schemas is not bound for this workspace.${missing}\n\nBind now? (reason=${options.reason})`,
		"Bind yaml.schemas",
		"Not now",
		"Never ask again",
	);
	if (choice === "Never ask again") {
		await context.workspaceState.update(WORKSPACE_STATE_SCHEMA_BINDING_NEVER_PROMPT, true);
		return false;
	}
	if (choice !== "Bind yaml.schemas") {
		return false;
	}

	await applyYamlSchemasBinding(schemaPaths);
	return true;
}

async function maybePromptBindSchemas(
	context: vscode.ExtensionContext,
	schemaPaths: { scalimYaml: string; demand: string; workflow: string },
): Promise<void> {
	void bindSchemasWithUserConfirmation(context, schemaPaths, {
		reason: "autoSchemaBinding",
		promptOncePerSession: true,
	});
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
		logWarn(`[schema] Failed to read required keys from schema: ${schemaPath}`);
		logWarn(String(e));
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

function updateDiscoveryFromPayload(payload: unknown): void {
	lastDiscovery = summarizeDiscoveryPayload(payload);
	if (!lastDiscovery) {
		return;
	}
	if (lastDiscovery.projectRoot) {
		lastProjectRoot = lastDiscovery.projectRoot;
	}
	const scalimYaml = lastDiscovery.scalimYamlPath;
	if (typeof scalimYaml === "string" && scalimYaml.trim()) {
		lastScalimYamlPath = scalimYaml.trim();
	} else {
		lastScalimYamlPath = undefined;
	}
}

async function dumpDiscovery(
	output: vscode.OutputChannel,
	env: ProvisionedEnv,
): Promise<unknown | undefined> {
	const editor = vscode.window.activeTextEditor;
	if (!editor) {
		logWarn("[diag] No active editor. Open a YAML file to dump discovery.");
		return undefined;
	}
	if (editor.document.uri.scheme !== "file") {
		logWarn(`[diag] Active document is not a file: ${editor.document.uri.toString()}`);
		return undefined;
	}

	const yamlPath = editor.document.uri.fsPath;
	const result = await runCommand(env.scalimYamlDslLspPath, ["dump-discovery", yamlPath, "--json"]);
	if (result.exitCode !== 0) {
		logError(`[diag] dump-discovery failed (exit=${result.exitCode}).`);
		logError(result.stderr.trim());
		return undefined;
	}
	try {
		const payload = JSON.parse(result.stdout) as unknown;
		updateDiscoveryFromPayload(payload);
		logInfo(`[diag] dump-discovery(${yamlPath}) = ${JSON.stringify(payload, null, 2)}`);
		return payload;
	} catch (e) {
		logWarn("[diag] dump-discovery returned non-JSON payload.");
		logWarn(result.stdout.trim());
		return undefined;
	}
}

async function dumpDiscoveryFromServer(
	output: vscode.OutputChannel,
	documentUri: string,
): Promise<unknown | undefined> {
	try {
		const payload = (await vscode.commands.executeCommand("scalim.dumpDiscovery", documentUri)) as unknown;
		updateDiscoveryFromPayload(payload);
		logInfo(`[diag] lsp dumpDiscovery(${documentUri}) = ${JSON.stringify(payload, null, 2)}`);
		return payload;
	} catch (e) {
		logWarn("[diag] lsp dumpDiscovery failed.");
		logWarn(String(e));
		return undefined;
	}
}

async function stopClient(output: vscode.OutputChannel): Promise<void> {
	if (!currentClient) {
		return;
	}
	const client = currentClient;
	expectedStoppedClients.add(client);
	try {
		await client.stop();
	} finally {
		if (currentClient === client) {
			currentClient = undefined;
		}
		logInfo("[lsp] Client stopped.");
	}
}

async function startClient(
	context: vscode.ExtensionContext,
	output: vscode.OutputChannel,
	env: ProvisionedEnv,
): Promise<void> {
	await stopClient(output);

	setStatusBarState(context, "starting", env);

	const cfg = getExtensionConfig();

	const serverArgs: string[] = ["serve"];
	if (serverLogPath) {
		serverArgs.push("--log-file", serverLogPath);
	}
	serverArgs.push("--log-level", cfg.serverLogLevel);
	const serverDebounceMs = Number.isFinite(cfg.serverDebounceMs) ? Math.max(0, Math.min(5000, Math.round(cfg.serverDebounceMs))) : 200;

	const serverOptions: ServerOptions = {
		command: env.scalimYamlDslLspPath,
		args: serverArgs,
		options: {
			cwd: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,
			env: {
				...process.env,
				SCALIM_YAML_DSL_LSP_DID_CHANGE_DEBOUNCE_MS: String(serverDebounceMs),
			},
		},
	};

	const clientOptions: LanguageClientOptions = {
		documentSelector: [
			{ language: "yaml", scheme: "file" },
			{ language: "yaml", scheme: "untitled" },
		],
		outputChannel: output,
		traceOutputChannel: ensureLspTraceOutputChannel(context),
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
				logInfo(`[lsp] executeCommand: ${command} args=${summarizeArgs(args)}`);
				try {
					const result = await Promise.resolve(next(command, args));
					logInfo(`[lsp] executeCommand ok: ${command}`);
					if (command === "scalim.python.explainResolutionFailure" && typeof result === "object" && result !== null) {
						const trace = (result as Record<string, unknown>)["trace"];
						if (trace !== undefined) {
							lastResolutionTrace = trace;
						}
					}
					if (command.startsWith("scalim.yaml.")) {
						void dumpDiscovery(output, env);
					}
					return result;
				} catch (e) {
					logError(`[lsp] executeCommand failed: ${command}`);
					logError(String(e));
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
			if (event.newState === State.Stopped && !expectedStoppedClients.has(client)) {
				logError("[lsp] Server stopped unexpectedly. Use 'Scalim: Restart Server' to recover.");
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

	logInfo(`[lsp] Starting: ${env.scalimYamlDslLspPath} ${serverArgs.join(" ")}`);
	try {
		await client.start();
		try {
			await client.setTrace(lspTraceLevelToProtocolTrace(cfg.lspTrace));
		} catch (e) {
			logWarn(`[lsp] Failed to apply lspTrace=${cfg.lspTrace}: ${String(e)}`);
		}
		logInfo("[lsp] Ready.");
		setStatusBarState(context, "running", env);
	} catch (e) {
		lastStartError = String(e);
		logError("[lsp] Failed to start.");
		logError(String(e));
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
				logInfo("[cmd] Reinstall server requested (rebuild venv).");
				currentEnv = undefined;
				try {
					const storagePath = context.globalStorageUri.fsPath;
					const venvPath = path.join(storagePath, "scalim-yaml-dsl-lsp-venv");
					await fsp.rm(venvPath, { recursive: true, force: true });
				} catch (e) {
					logWarn(`[cmd] Failed to remove venv: ${String(e)}`);
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
					logInfo("[workspace] envMode=auto but workspace venv not usable; trying PATH next.");
				}
			}

			if (!env && (envMode === "auto" || envMode === "path")) {
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
					logWarn("[python] No suitable python found.");
					return;
				}

				env = await ensureVenv(context, output, py.pythonPath, pinnedServerSpec, allowInstall);
			}

			if (!env) {
				setStatusBarState(context, "stopped", currentEnv);

				const installCmd = `uv tool install "${pinnedServerSpec}"`;
				logError("[env] No usable server environment found.");
				logInfo(`[env] Install (recommended): ${installCmd}`);

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
					await maybePromptBindSchemas(context, schemaPaths);
				} else {
					logInfo("[schema] autoSchemaBinding=false; skipping workspace yaml.schemas update.");
				}
			} catch (e) {
				logWarn(`[schema] Skipping schema binding. err=${String(e)}`);
			}

			await startClient(context, output, env);
		} catch (e) {
			lastStartError = String(e);
			logError("[error] Failed to provision/start Scalim YAML DSL.");
			logError(lastStartError);
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
		logInfo("[mutex] Restart already in progress; waiting...");
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
	logInfo("[env] No provisioned environment yet; provisioning first.");
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
	const workspaceRoot = resolveWorkspaceRoot();

	const editorPath =
		vscode.window.activeTextEditor?.document.uri.scheme === "file"
			? vscode.window.activeTextEditor.document.uri.fsPath
			: undefined;
	const startDir = editorPath ? path.dirname(editorPath) : workspaceRoot;

	if (startDir) {
		const nearest = findNearestScalimYamlUpwards(startDir, workspaceRoot);
		if (nearest) {
			lastScalimYamlPath = nearest;
			const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(nearest));
			await vscode.window.showTextDocument(doc, { preview: false });
			setStatusBarState(context, currentStatusBarState(), currentEnv);
			return;
		}
	}

	const uris = await findWorkspaceScalimYamlUris(20);
	if (uris.length) {
		lastScalimYamlPath = uris[0].fsPath;
		const doc = await vscode.workspace.openTextDocument(uris[0]);
		await vscode.window.showTextDocument(doc, { preview: false });
		setStatusBarState(context, currentStatusBarState(), currentEnv);
		return;
	}

	if (!workspaceRoot) {
		void vscode.window.showErrorMessage("Scalim: no workspace folder is open.");
		return;
	}

	const createdPath = path.join(workspaceRoot, "scalim.yaml");
	const choice = await vscode.window.showInformationMessage(
		`Scalim: scalim.yaml not found. Create a minimal template at:\n${createdPath}`,
		"Create scalim.yaml",
		"Cancel",
	);
	if (choice !== "Create scalim.yaml") {
		return;
	}

	logInfo(`[cmd] Creating scalim.yaml template: ${createdPath}`);
	const ok = await createScalimYamlTemplateFile(createdPath);
	if (!ok) {
		void vscode.window.showErrorMessage("Scalim: failed to create scalim.yaml (workspace edit was not applied).");
		return;
	}

	lastScalimYamlPath = createdPath;
	const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(createdPath));
	await vscode.window.showTextDocument(doc, { preview: false });
	setStatusBarState(context, currentStatusBarState(), currentEnv);
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
	updateActiveDocumentKindAndRefreshStatusBar(context, document);
	if (!isLikelyScalimYamlDslDocument(document)) {
		return;
	}

	if (clientIsRunningOrStarting() || startMutex) {
		return;
	}
	if (autoStartAttempted && !currentClient) {
		return;
	}

	autoStartAttempted = true;
	logInfo(`[auto] Detected Scalim YAML DSL document: ${document.uri.toString()}`);
	await restartServer(context, output, /*reinstall*/ false, /*allowInstall*/ false);

	// Schema binding is handled via Doctor / Setup Wizard (requires user confirmation).
}

async function openServerLogFile(context: vscode.ExtensionContext): Promise<void> {
	const logPath = serverLogPath ?? path.join(context.globalStorageUri.fsPath, "server.log");
	try {
		await fsp.mkdir(path.dirname(logPath), { recursive: true });
		if (!fs.existsSync(logPath)) {
			await fsp.writeFile(logPath, "", "utf8");
		}
		const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(logPath));
		await vscode.window.showTextDocument(doc, { preview: false });
	} catch (e) {
		logWarn(`[logs] Failed to open server log file: ${String(e)}`);
		void vscode.window.showErrorMessage("Scalim: failed to open server log file. See extension logs for details.");
	}
}

async function openExtensionLogFile(context: vscode.ExtensionContext): Promise<void> {
	const logPath = extensionLogPath ?? path.join(context.globalStorageUri.fsPath, "extension.log");
	try {
		await fsp.mkdir(path.dirname(logPath), { recursive: true });
		if (!fs.existsSync(logPath)) {
			await fsp.writeFile(logPath, "", "utf8");
		}
		const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(logPath));
		await vscode.window.showTextDocument(doc, { preview: false });
	} catch (e) {
		logWarn(`[logs] Failed to open extension log file: ${String(e)}`);
		void vscode.window.showErrorMessage("Scalim: failed to open extension log file. See OutputChannel for details.");
	}
}

function currentLspStatusLabel(): string {
	const state = clientState();
	if (state === State.Running) {
		return "running";
	}
	if (state === State.Starting || startMutex) {
		return "starting";
	}
	return "stopped";
}

async function findWorkspaceScalimYamlUris(maxResults = 20): Promise<vscode.Uri[]> {
	return await vscode.workspace.findFiles("**/scalim.yaml", "**/.tmp/**", maxResults);
}

function findNearestScalimYamlUpwards(startDir: string, stopDir: string | undefined): string | undefined {
	let current = path.resolve(startDir);
	const stop = stopDir ? path.resolve(stopDir) : undefined;

	while (true) {
		const candidate = path.join(current, "scalim.yaml");
		if (fs.existsSync(candidate)) {
			return candidate;
		}
		if (stop && current === stop) {
			return undefined;
		}
		const parent = path.dirname(current);
		if (parent === current) {
			return undefined;
		}
		current = parent;
	}
}

function parseYamlScalar(text: string): string {
	const trimmed = String(text || "").trim();
	if (!trimmed) {
		return "";
	}
	if (
		(trimmed.startsWith("\"") && trimmed.endsWith("\"") && trimmed.length >= 2) ||
		(trimmed.startsWith("'") && trimmed.endsWith("'") && trimmed.length >= 2)
	) {
		return trimmed.slice(1, -1);
	}
	return trimmed;
}

function parseImportRootsFromScalimYamlText(rawText: string): { path: string; alias?: string | null }[] | undefined {
	const lines = String(rawText || "").split(/\r?\n/);

	let importRootsIndent: number | undefined;
	let listIndent: number | undefined;
	let currentItem: { path?: string; alias?: string | null } | undefined;
	const out: { path: string; alias?: string | null }[] = [];

	const flush = (): void => {
		if (currentItem?.path) {
			out.push({ path: currentItem.path, alias: currentItem.alias });
		}
		currentItem = undefined;
	};

	for (const line of lines) {
		const trimmed = line.trim();
		if (!trimmed || trimmed.startsWith("#")) {
			continue;
		}
		const indent = line.length - line.trimStart().length;

		if (importRootsIndent === undefined) {
			if (/^import_roots\s*:/.test(trimmed)) {
				importRootsIndent = indent;
			}
			continue;
		}

		if (indent <= importRootsIndent) {
			break;
		}

		if (listIndent === undefined) {
			const m = trimmed.match(/^-\s*(.*)$/);
			if (!m) {
				continue;
			}
			listIndent = indent;
			currentItem = {};
			const rest = m[1].trim();
			if (rest) {
				const kv = rest.match(/^(path|alias)\s*:\s*(.*)$/);
				if (kv) {
					const key = kv[1];
					const value = parseYamlScalar(kv[2] || "");
					if (key === "path") {
						currentItem.path = value;
					} else if (key === "alias") {
						currentItem.alias = value || null;
					}
				}
			}
			continue;
		}

		if (indent === listIndent && /^-/.test(trimmed)) {
			flush();
			currentItem = {};
			const rest = trimmed.replace(/^-/, "").trim();
			if (rest) {
				const kv = rest.match(/^(path|alias)\s*:\s*(.*)$/);
				if (kv) {
					const key = kv[1];
					const value = parseYamlScalar(kv[2] || "");
					if (key === "path") {
						currentItem.path = value;
					} else if (key === "alias") {
						currentItem.alias = value || null;
					}
				}
			}
			continue;
		}

		if (!currentItem) {
			continue;
		}

		const kv = trimmed.match(/^(path|alias)\s*:\s*(.*)$/);
		if (!kv) {
			continue;
		}
		const key = kv[1];
		const value = parseYamlScalar(kv[2] || "");
		if (key === "path") {
			currentItem.path = value;
		} else if (key === "alias") {
			currentItem.alias = value || null;
		}
	}

	flush();
	return out.length ? out : undefined;
}

function renderMinimalScalimYamlTemplate(): string {
	return [
		"# Scalim project config (scalim.yaml)",
		"# NOTE: This file is optional. Keep it minimal; do not put secrets here.",
		"",
		"yaml_dsl:",
		"  import_roots:",
		"    - path: .",
		"      alias: '@'",
		"  lsp:",
		"    python_roots:",
		"      - .",
		"",
	].join("\n");
}

async function createScalimYamlTemplateFile(targetPath: string): Promise<boolean> {
	const uri = vscode.Uri.file(targetPath);
	try {
		await vscode.workspace.fs.stat(uri);
		return true;
	} catch {
		// continue
	}

	const edit = new vscode.WorkspaceEdit();
	edit.createFile(uri, { ignoreIfExists: true });
	edit.insert(uri, new vscode.Position(0, 0), renderMinimalScalimYamlTemplate());
	const ok = await vscode.workspace.applyEdit(edit);
	return ok;
}

async function refreshScalimYamlCache(): Promise<void> {
	const uris = await findWorkspaceScalimYamlUris(20);
	const first = uris[0]?.fsPath;
	lastScalimYamlPath = first ? first : undefined;
	if (lastDiscovery && !lastScalimYamlPath) {
		lastDiscovery.scalimYamlPath = null;
	}
}

async function copyDiagnosticBundle(context: vscode.ExtensionContext, output: vscode.OutputChannel): Promise<void> {
	const cfg = getExtensionConfig();
	const env = currentEnv;

	if (!lastDiscovery) {
		const editor = vscode.window.activeTextEditor;
		if (editor?.document.uri.scheme === "file") {
			await dumpDiscoveryFromServer(output, editor.document.uri.toString());
		}
	}

	let discovery: DiscoverySummary | undefined = lastDiscovery;
	const scalimYaml = lastScalimYamlPath ?? (typeof discovery?.scalimYamlPath === "string" ? discovery.scalimYamlPath : undefined);
	if (scalimYaml) {
		try {
			const raw = await fsp.readFile(scalimYaml, "utf8");
			const importRoots = parseImportRootsFromScalimYamlText(raw);
			discovery = { ...(discovery ?? {}), importRoots };
		} catch {
			// ignore
		}
	}

	const configuredPinnedServerSpec = cfg.pinnedServerSpec;
	const activeServerSpec = env?.pinnedServerSpec;
	let expectedServerVersion: string | undefined;
	if (env?.kind === "pinnedVenv") {
		expectedServerVersion = extractPinnedVersion(activeServerSpec || "");
		if (!expectedServerVersion) {
			expectedServerVersion = "<latest>";
		}
	} else {
		expectedServerVersion = "<n/a>";
	}
	let yamlSchemasBound: boolean | undefined;
	let yamlSchemasStatus: string | undefined;

	if (env?.schemaPaths) {
		const existing = vscode.workspace.getConfiguration().get<unknown>("yaml.schemas");
		const additions = {
			[env.schemaPaths.scalimYaml]: ["scalim.yaml"],
			[env.schemaPaths.demand]: ["demand/**/*.y*ml"],
			[env.schemaPaths.workflow]: ["workflow/**/*.y*ml"],
		};
		const status = yamlSchemasBindingStatus(existing, additions);
		yamlSchemasBound = status.bound;
		yamlSchemasStatus = status.bound ? "ok" : `missing=${status.missing.length}`;
	}

	const bundle = renderDiagnosticBundle({
		timestampIso: getNowIso(),
		extensionVersion: String(context.extension.packageJSON.version || ""),
		vscodeVersion: vscode.version,
		envKind: env?.kind,
		envMode: cfg.envMode,
		configuredPinnedServerSpec,
		activeServerSpec,
		expectedServerVersion,
		serverPackageVersion: env?.serverPackageVersion,
		pythonPath: env?.pythonPath,
		pythonVersion: env?.pythonVersion,
		lspStatus: currentLspStatusLabel(),
		lastStartError,
		discovery,
		yamlSchemasBound,
		yamlSchemasStatus,
		lastResolutionTrace,
		extensionLogPath,
		serverLogPath,
	});

	await vscode.env.clipboard.writeText(bundle);
	logInfo("[diag] Diagnostic bundle copied to clipboard.");

	void vscode.window
		.showInformationMessage("Scalim: diagnostic bundle copied to clipboard.", "Open logs", "Open server log file", "Open extension log file")
		.then((choice) => {
			if (choice === "Open logs") {
				output.show(true);
			}
			if (choice === "Open server log file") {
				void openServerLogFile(context);
			}
			if (choice === "Open extension log file") {
				void openExtensionLogFile(context);
			}
		});
}

type DoctorAction = {
	title: string;
	run: () => Promise<void>;
};

type DoctorCheck = {
	id: string;
	title: string;
	ok: boolean;
	message: string;
	actions: DoctorAction[];
};

function formatDoctorReport(checks: readonly DoctorCheck[]): string {
	const lines: string[] = [];
	for (const check of checks) {
		const flag = check.ok ? "PASS" : "FAIL";
		lines.push(`[${flag}] ${check.title}: ${check.message}`);
	}
	return lines.join("\n");
}

async function runDoctor(context: vscode.ExtensionContext, output: vscode.OutputChannel): Promise<void> {
	logInfo("[doctor] Running doctor...");

	const cfg = getExtensionConfig();
	const checks: DoctorCheck[] = [];

	// 1) Python version
	const py = await detectPython(output, cfg.pythonPathOverride);
	if (!py) {
		checks.push({
			id: "python",
			title: "Python >= 3.10",
			ok: false,
			message: "No suitable python found (need >=3.10).",
			actions: [
				{
					title: "Open settings",
					run: async () => {
						await vscode.commands.executeCommand("workbench.action.openSettings", "scalim.yamlDsl.pythonPath");
					},
				},
				{
					title: "Setup Wizard",
					run: async () => {
						await setupWizard(context, output);
					},
				},
			],
		});
	} else {
		checks.push({
			id: "python",
			title: "Python >= 3.10",
			ok: true,
			message: `${py.pythonPath} (${py.pythonVersionRaw})`,
			actions: [],
		});
	}

	// 2) Server installed/version
	if (!currentEnv) {
		checks.push({
			id: "server",
			title: "LSP server installed",
			ok: false,
			message: "No provisioned environment yet.",
			actions: [
				{
					title: "Setup Wizard",
					run: async () => {
						await setupWizard(context, output);
					},
				},
				{
					title: "Restart server",
					run: async () => {
						await restartServer(context, output, /*reinstall*/ false, /*allowInstall*/ false);
					},
				},
			],
		});
	} else {
		const expectedVersion = currentEnv.kind === "pinnedVenv" ? extractPinnedVersion(currentEnv.pinnedServerSpec) : undefined;

		if (currentEnv.kind === "pinnedVenv" && !currentEnv.serverPackageVersion) {
			checks.push({
				id: "server",
				title: "LSP server installed",
				ok: false,
				message: "Unable to detect server package version.",
				actions: [
					{
						title: "Reinstall server",
						run: async () => {
							await restartServer(context, output, /*reinstall*/ true, /*allowInstall*/ true);
						},
					},
					{
						title: "Setup Wizard",
						run: async () => {
							await setupWizard(context, output);
						},
					},
				],
			});
			// continue
		} else if (expectedVersion && currentEnv.serverPackageVersion !== expectedVersion) {
			checks.push({
				id: "server",
				title: "LSP server version matches pinned spec",
				ok: false,
				message: `expected=${expectedVersion} actual=${currentEnv.serverPackageVersion}`,
				actions: [
					{
						title: "Reinstall server",
						run: async () => {
							await restartServer(context, output, /*reinstall*/ true, /*allowInstall*/ true);
						},
					},
					{
						title: "Setup Wizard",
						run: async () => {
							await setupWizard(context, output);
						},
					},
				],
			});
		} else {
			checks.push({
				id: "server",
				title: "LSP server installed",
				ok: true,
				message: currentEnv.serverPackageVersion ?? "<unknown>",
				actions: [],
			});
		}
	}

	// 3) scalim.yaml
	const scalimYamlUris = await findWorkspaceScalimYamlUris(20);
	if (!scalimYamlUris.length) {
		checks.push({
			id: "scalimYaml",
			title: "scalim.yaml exists",
			ok: false,
			message: "No scalim.yaml found in workspace.",
			actions: [
				{
					title: "Create scalim.yaml",
					run: async () => {
						await openOrCreateScalimYaml(context, output);
					},
				},
			],
		});
	} else {
		lastScalimYamlPath = scalimYamlUris[0].fsPath;
		checks.push({
			id: "scalimYaml",
			title: "scalim.yaml exists",
			ok: true,
			message: scalimYamlUris[0].fsPath,
			actions: [
				{
					title: "Open scalim.yaml",
					run: async () => {
						const doc = await vscode.workspace.openTextDocument(scalimYamlUris[0]);
						await vscode.window.showTextDocument(doc, { preview: false });
					},
				},
			],
		});
	}

	// 4) yaml.schemas binding
	let schemaPaths = currentEnv?.schemaPaths;
	if (!schemaPaths && currentEnv?.scalimCliPath) {
		try {
			schemaPaths = await resolveSchemaPaths(output, currentEnv.scalimCliPath);
		} catch {
			// ignore
		}
	}

	if (!schemaPaths) {
		checks.push({
			id: "yamlSchemas",
			title: "yaml.schemas binding",
			ok: false,
			message: "Unable to resolve schema paths (need scalim-cli).",
			actions: [
				{
					title: "Setup Wizard",
					run: async () => {
						await setupWizard(context, output);
					},
				},
			],
		});
	} else {
		const existing = vscode.workspace.getConfiguration().get<unknown>("yaml.schemas");
		const additions = {
			[schemaPaths.scalimYaml]: ["scalim.yaml"],
			[schemaPaths.demand]: ["demand/**/*.y*ml"],
			[schemaPaths.workflow]: ["workflow/**/*.y*ml"],
		};
		const status = yamlSchemasBindingStatus(existing, additions);
		checks.push({
			id: "yamlSchemas",
			title: "yaml.schemas binding",
			ok: status.bound,
			message: status.bound ? "ok" : `missing=${status.missing.length}`,
			actions: [
				{
					title: "Bind yaml.schemas",
					run: async () => {
						await bindSchemasWithUserConfirmation(context, schemaPaths!, {
							reason: "doctor",
							promptOncePerSession: false,
						});
					},
				},
			],
		});
	}

	// 5) Server running
	if (clientState() === State.Running) {
		checks.push({
			id: "serverRunning",
			title: "LSP server running",
			ok: true,
			message: "running",
			actions: [],
		});
	} else {
		checks.push({
			id: "serverRunning",
			title: "LSP server running",
			ok: false,
			message: `status=${currentLspStatusLabel()}${lastStartError ? ` lastStartError=${lastStartError}` : ""}`,
			actions: [
				{
					title: "Restart server",
					run: async () => {
						await restartServer(context, output, /*reinstall*/ false, /*allowInstall*/ false);
					},
				},
				{
					title: "Setup Wizard",
					run: async () => {
						await setupWizard(context, output);
					},
				},
			],
		});
	}

	logInfo("[doctor] Report:\n" + formatDoctorReport(checks));
	output.show(true);

	const firstFail = checks.find((c) => !c.ok);
	if (!firstFail) {
		void vscode.window.showInformationMessage("Scalim: Doctor passed. All checks OK.", "Copy Diagnostic Bundle", "Open logs").then((choice) => {
			if (choice === "Copy Diagnostic Bundle") {
				void copyDiagnosticBundle(context, output);
			}
			if (choice === "Open logs") {
				output.show(true);
			}
		});
	} else {
		const actionTitles = firstFail.actions.map((a) => a.title);
		void vscode.window
			.showWarningMessage(`Scalim: Doctor failed: ${firstFail.title}: ${firstFail.message}`, ...actionTitles, "Copy Diagnostic Bundle", "Open logs")
			.then((choice) => {
				if (!choice) {
					return;
				}
				if (choice === "Copy Diagnostic Bundle") {
					void copyDiagnosticBundle(context, output);
					return;
				}
				if (choice === "Open logs") {
					output.show(true);
					return;
				}
				const action = firstFail.actions.find((a) => a.title === choice);
				if (action) {
					void action.run();
				}
			});
	}

	setStatusBarState(context, currentStatusBarState(), currentEnv);
}

async function setupWizard(context: vscode.ExtensionContext, output: vscode.OutputChannel): Promise<void> {
	logInfo("[wizard] Starting setup wizard...");
	const cfg = getExtensionConfig();

	const modePick = await vscode.window.showQuickPick(
		[
			{ label: "Extension venv (recommended)", description: "Isolated venv under extension globalStorage", mode: "pinnedVenv" as const },
			{ label: "Workspace venv", description: "Reuse an existing venv in the workspace", mode: "workspaceVenv" as const },
			{ label: "PATH", description: "Use scalim-yaml-dsl-lsp from PATH", mode: "path" as const },
		],
		{ placeHolder: "Scalim: choose server provisioning mode" },
	);
	if (!modePick) {
		return;
	}

	const pinnedSpecInput = await vscode.window.showInputBox({
		prompt: "Pinned server spec (pip requirement). Leave empty to use the configured default.",
		value: cfg.pinnedServerSpec || DEFAULT_PINNED_SERVER_SPEC,
	});
	if (pinnedSpecInput === undefined) {
		return;
	}
	const pinnedSpec = (pinnedSpecInput || "").trim() || cfg.pinnedServerSpec || DEFAULT_PINNED_SERVER_SPEC;

	const workspaceRoot = resolveWorkspaceRoot();
	const venvPath = workspaceRoot ? resolveWorkspaceVenvPath(workspaceRoot, cfg.workspaceVenvPath) : undefined;
	const installCmd = `uv tool install "${pinnedSpec}"`;

	const summaryLines: string[] = [
		`mode: ${modePick.mode}`,
		`pinnedSpec: ${pinnedSpec}`,
		modePick.mode === "pinnedVenv"
			? `action: create/upgrade venv under globalStorage (${context.globalStorageUri.fsPath})`
			: modePick.mode === "workspaceVenv"
				? `action: install/upgrade into workspace venv (${venvPath ?? "<no-workspace>"})`
				: `action: ensure PATH contains scalim-yaml-dsl-lsp (recommended: ${installCmd})`,
	];

	const confirm = await vscode.window.showInformationMessage(`Scalim: Setup Wizard\n\n${summaryLines.join("\n")}\n\nProceed?`, "Proceed", "Cancel");
	if (confirm !== "Proceed") {
		return;
	}

	const extCfg = vscode.workspace.getConfiguration("scalim.yamlDsl");
	await extCfg.update("envMode", modePick.mode, vscode.ConfigurationTarget.Workspace);
	await extCfg.update("pinnedServerSpec", pinnedSpec, vscode.ConfigurationTarget.Workspace);

	try {
		if (modePick.mode === "workspaceVenv") {
			if (!workspaceRoot) {
				throw new Error("No workspace folder is open (required for workspace venv mode).");
			}
			const venvPythonPath =
				findVenvExecutable(venvPath ?? "", "python") ??
				findVenvExecutable(venvPath ?? "", "python3") ??
				(venvPath ? path.join(getVenvScriptsDir(venvPath), isWindows() ? "python.exe" : "python") : "");
			if (!venvPythonPath || !fs.existsSync(venvPythonPath)) {
				throw new Error(`Workspace venv python not found: ${venvPythonPath}`);
			}
			logInfo(`[wizard] Installing server into workspace venv: ${pinnedSpec}`);
			const installResult = await runCommand(venvPythonPath, ["-m", "pip", "install", "--upgrade", pinnedSpec], { cwd: workspaceRoot });
			if (installResult.exitCode !== 0) {
				throw new Error(`pip install failed (exit=${installResult.exitCode}): ${installResult.stderr.trim()}`);
			}
		}

		if (modePick.mode === "path") {
			const lspHelp = await runCommand("scalim-yaml-dsl-lsp", ["--help"]);
			if (lspHelp.exitCode !== 0) {
				await vscode.env.clipboard.writeText(installCmd);
				void vscode.window.showWarningMessage(
					"Scalim: scalim-yaml-dsl-lsp is not in PATH. Install command copied to clipboard.",
					"Open terminal",
				).then((choice) => {
					if (choice === "Open terminal") {
						const term = vscode.window.createTerminal("Scalim YAML DSL");
						term.show(true);
						term.sendText(installCmd, false);
					}
				});
			}
		}

		await restartServer(context, output, /*reinstall*/ false, /*allowInstall*/ true);
		await runDoctor(context, output);
	} catch (e) {
		const err = String(e);
		logError(`[wizard] Failed: ${err}`);
		await vscode.env.clipboard.writeText(err);
		void vscode.window
			.showErrorMessage(
				"Scalim: Setup Wizard failed (error copied to clipboard).",
				"Open logs",
				"Switch to Extension venv",
				"Switch to PATH",
			)
			.then((choice) => {
				if (choice === "Open logs") {
					output.show(true);
				}
				if (choice === "Switch to Extension venv") {
					void vscode.workspace.getConfiguration("scalim.yamlDsl").update("envMode", "pinnedVenv", vscode.ConfigurationTarget.Workspace);
				}
				if (choice === "Switch to PATH") {
					void vscode.workspace.getConfiguration("scalim.yamlDsl").update("envMode", "path", vscode.ConfigurationTarget.Workspace);
				}
			});
	}
}

async function openStatusMenu(context: vscode.ExtensionContext, output: vscode.OutputChannel): Promise<void> {
	const items: Array<{ label: string; description: string; run: () => Promise<void> }> = [
		{ label: "Open Logs", description: "Show OutputChannel", run: async () => output.show(true) },
		{
			label: "Open LSP Trace Output",
			description: "Show LSP wire trace channel (may contain YAML contents)",
			run: async () => ensureLspTraceOutputChannel(context).show(true),
		},
		{ label: "Open Server Log File", description: "Open globalStorage/server.log", run: async () => await openServerLogFile(context) },
		{ label: "Open Extension Log File", description: "Open globalStorage/extension.log", run: async () => await openExtensionLogFile(context) },
		{ label: "Copy Diagnostic Bundle", description: "Copy a redacted report", run: async () => await copyDiagnosticBundle(context, output) },
		{ label: "Show Discovery Summary", description: "Print dump-discovery to OutputChannel", run: async () => await vscode.commands.executeCommand("scalim.yamlDsl.showDiscoverySummary") },
		{ label: "Open scalim.yaml", description: "Find nearest or create template", run: async () => await vscode.commands.executeCommand("scalim.yamlDsl.openOrCreateScalimYaml") },
		{ label: "Doctor", description: "Run preflight checks", run: async () => await runDoctor(context, output) },
		{ label: "Setup Wizard", description: "Provision + configure", run: async () => await setupWizard(context, output) },
		{ label: "Restart Server", description: "Restart LSP server", run: async () => await restartServer(context, output, false, false) },
		{ label: "Reinstall Server", description: "Rebuild pinned venv", run: async () => await restartServer(context, output, true, true) },
	];

	const picked = await vscode.window.showQuickPick(items, { placeHolder: "Scalim" });
	if (!picked) {
		return;
	}
	await picked.run();
}

async function handleScalimYamlChanged(context: vscode.ExtensionContext, output: vscode.OutputChannel, kind: string): Promise<void> {
	await refreshScalimYamlCache();
	setStatusBarState(context, currentStatusBarState(), currentEnv);

	const cfg = getExtensionConfig();
	const message = `Scalim: scalim.yaml ${kind}. Restart LSP server?`;

	if (cfg.autoRestartOnScalimYamlChange) {
		logInfo("[watcher] autoRestartOnScalimYamlChange=true; restarting server.");
		void restartServer(context, output, /*reinstall*/ false, /*allowInstall*/ false);
		return;
	}

	const choice = await vscode.window.showInformationMessage(message, "Restart server", "Open scalim.yaml", "Enable auto restart");
	if (choice === "Restart server") {
		await restartServer(context, output, /*reinstall*/ false, /*allowInstall*/ false);
		return;
	}
	if (choice === "Open scalim.yaml") {
		await openOrCreateScalimYaml(context, output);
		return;
	}
	if (choice === "Enable auto restart") {
		await vscode.workspace
			.getConfiguration("scalim.yamlDsl")
			.update("autoRestartOnScalimYamlChange", true, vscode.ConfigurationTarget.Workspace);
		void vscode.window.showInformationMessage("Scalim: auto restart enabled for scalim.yaml changes.");
	}
}

function registerPresetVirtualDocuments(context: vscode.ExtensionContext): void {
	const provider: vscode.TextDocumentContentProvider = {
		provideTextDocumentContent: async (uri) => {
			const presetId = decodeURIComponent(uri.path.replace(/^\/+/, ""));
			if (!presetId) {
				return "# Invalid scalim preset uri (missing presetId)\n";
			}
			try {
				const payload = (await vscode.commands.executeCommand("scalim.preset.getText", presetId)) as unknown;
				if (payload && typeof payload === "object") {
					const obj = payload as { ok?: boolean; content?: string; message?: string };
					if (obj.ok && typeof obj.content === "string") {
						return obj.content;
					}
					if (typeof obj.message === "string" && obj.message.trim()) {
						return `# Failed to load preset: ${obj.message}\n`;
					}
				}
				return "# Failed to load preset (unknown server response)\n";
			} catch (err) {
				return `# Failed to load preset: ${String(err)}\n`;
			}
		},
	};

	context.subscriptions.push(vscode.workspace.registerTextDocumentContentProvider(PRESET_VDOC_SCHEME, provider));
	context.subscriptions.push(
		vscode.workspace.onDidOpenTextDocument((document) => {
			if (document.uri.scheme !== PRESET_VDOC_SCHEME) {
				return;
			}
			if (document.languageId !== "yaml") {
				void vscode.languages.setTextDocumentLanguage(document, "yaml");
			}
		}),
	);
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
	const output = vscode.window.createOutputChannel("Scalim YAML DSL");
	context.subscriptions.push(output);

	outputChannelForLogs = output;
	extensionLogThreshold = getExtensionConfig().logLevel;
	await initializeLogFiles(context);

	logInfo("[activate] Scalim YAML DSL extension activated.");
	lastProjectRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? lastProjectRoot;
	await refreshScalimYamlCache();
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
		vscode.commands.registerCommand("scalim.yamlDsl.openStatusMenu", async () => {
			await openStatusMenu(context, output);
		}),
	);

	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.openServerLogFile", async () => {
			await openServerLogFile(context);
		}),
	);

	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.copyDiagnosticBundle", async () => {
			await copyDiagnosticBundle(context, output);
		}),
	);

	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.doctor", async () => {
			await runDoctor(context, output);
		}),
	);

	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.setupWizard", async () => {
			await setupWizard(context, output);
		}),
	);

	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.showDiagnostics", async () => {
			const env = await ensureProvisionedEnv(context, output);
			if (!env) {
				return;
			}
			logInfo(
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
				]
					.filter((line): line is string => Boolean(line))
					.join("\n"),
			);
			if (env.schemaPaths) {
				logInfo(`[diag] schemaPaths=${JSON.stringify(env.schemaPaths, null, 2)}`);
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

	const watcher = vscode.workspace.createFileSystemWatcher("**/scalim.yaml");
	context.subscriptions.push(watcher);
	watcher.onDidCreate(() => {
		void handleScalimYamlChanged(context, output, "created");
	});
	watcher.onDidChange(() => {
		void handleScalimYamlChanged(context, output, "changed");
	});
	watcher.onDidDelete(() => {
		void handleScalimYamlChanged(context, output, "deleted");
	});

	context.subscriptions.push(
		vscode.workspace.onDidChangeConfiguration(async (event) => {
			const affectsLogLevel = event.affectsConfiguration("scalim.yamlDsl.logLevel");
			const affectsTrace = event.affectsConfiguration("scalim.yamlDsl.lspTrace");
			const affectsRestart =
				event.affectsConfiguration("scalim.yamlDsl.serverDebounceMs") ||
				event.affectsConfiguration("scalim.yamlDsl.serverLogLevel");

			if (affectsLogLevel) {
				extensionLogThreshold = getExtensionConfig().logLevel;
				logInfo(`[cfg] logLevel=${extensionLogThreshold}`);
			}

			if (affectsTrace && currentClient) {
				const cfg = getExtensionConfig();
				try {
					await currentClient.setTrace(lspTraceLevelToProtocolTrace(cfg.lspTrace));
					logInfo(`[cfg] lspTrace=${cfg.lspTrace}`);
				} catch (e) {
					logWarn(`[cfg] Failed to apply lspTrace: ${String(e)}`);
				}
			}

			if (!affectsRestart) {
				return;
			}
			if (!currentClient) {
				return;
			}

			const cfg = getExtensionConfig();
			const message = "Scalim: server settings changed. Restart LSP server to apply?";
			if (cfg.autoRestartOnSettingsChange) {
				logInfo("[watcher] autoRestartOnSettingsChange=true; restarting server.");
				void restartServer(context, output, /*reinstall*/ false, /*allowInstall*/ false);
				return;
			}

			const choice = await vscode.window.showInformationMessage(message, "Restart server", "Enable auto restart");
			if (choice === "Restart server") {
				await restartServer(context, output, /*reinstall*/ false, /*allowInstall*/ false);
				return;
			}
			if (choice === "Enable auto restart") {
				await vscode.workspace
					.getConfiguration("scalim.yamlDsl")
					.update("autoRestartOnSettingsChange", true, vscode.ConfigurationTarget.Workspace);
				void vscode.window.showInformationMessage("Scalim: auto restart enabled for settings changes.");
			}
		}),
	);

	registerPresetVirtualDocuments(context);

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
		const client = currentClient;
		expectedStoppedClients.add(client);
		try {
			await client.stop();
		} finally {
			currentClient = undefined;
		}
	}
}
