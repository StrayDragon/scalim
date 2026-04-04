import * as fs from "node:fs";
import * as fsp from "node:fs/promises";
import * as path from "node:path";

import * as vscode from "vscode";
import {
	LanguageClient,
	type LanguageClientOptions,
	type ServerOptions,
	State,
	TransportKind,
} from "vscode-languageclient/node";

import { runCommand } from "./internal/exec";
import { mergeYamlSchemas } from "./internal/yamlSchemas";

const DEFAULT_PINNED_SERVER_SPEC = "scalim-yaml-dsl-lsp[server]==0.7.5";

type Semver = {
	major: number;
	minor: number;
	patch: number;
};

type ProvisionedEnv = {
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
};

let currentClient: LanguageClient | undefined;
let currentEnv: ProvisionedEnv | undefined;
let expectedStop = false;
let startMutex: Promise<void> | undefined;

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

function getExtensionConfig(): {
	pythonPathOverride?: string;
	pinnedServerSpec: string;
	autoSchemaBinding: boolean;
} {
	const cfg = vscode.workspace.getConfiguration("scalim.yamlDsl");
	const pythonPathOverride = (cfg.get<string>("pythonPath") || "").trim() || undefined;
	const pinnedServerSpec = (cfg.get<string>("pinnedServerSpec") || "").trim() || DEFAULT_PINNED_SERVER_SPEC;
	const autoSchemaBinding = cfg.get<boolean>("autoSchemaBinding", true);
	return { pythonPathOverride, pinnedServerSpec, autoSchemaBinding };
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

async function ensureVenv(
	context: vscode.ExtensionContext,
	output: vscode.OutputChannel,
	pythonPath: string,
	pinnedServerSpec: string,
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

	const installArgs = ["-m", "pip", "install", "--upgrade", pinnedServerSpec];
	output.appendLine(`[pip] Installing pinned server: ${pinnedServerSpec}`);
	output.appendLine(`[pip] Command: ${venvPythonPath} ${installArgs.join(" ")}`);
	const installResult = await runCommand(venvPythonPath, installArgs, { cwd: storagePath });
	if (installResult.exitCode !== 0) {
		output.appendLine(`[pip] Install failed (exit=${installResult.exitCode})`);
		output.appendLine(installResult.stderr.trim());
		throw new Error("Failed to install pinned server");
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

async function dumpDiscovery(
	output: vscode.OutputChannel,
	env: ProvisionedEnv,
): Promise<void> {
	const editor = vscode.window.activeTextEditor;
	if (!editor) {
		output.appendLine("[diag] No active editor. Open a YAML file to dump discovery.");
		return;
	}
	if (editor.document.uri.scheme !== "file") {
		output.appendLine(`[diag] Active document is not a file: ${editor.document.uri.toString()}`);
		return;
	}

	const yamlPath = editor.document.uri.fsPath;
	const result = await runCommand(env.scalimYamlDslLspPath, ["dump-discovery", yamlPath, "--json"]);
	if (result.exitCode !== 0) {
		output.appendLine(`[diag] dump-discovery failed (exit=${result.exitCode}).`);
		output.appendLine(result.stderr.trim());
		return;
	}
	try {
		const payload = JSON.parse(result.stdout) as unknown;
		output.appendLine(`[diag] dump-discovery(${yamlPath}) = ${JSON.stringify(payload, null, 2)}`);
	} catch (e) {
		output.appendLine("[diag] dump-discovery returned non-JSON payload.");
		output.appendLine(result.stdout.trim());
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

	const serverOptions: ServerOptions = {
		command: env.scalimYamlDslLspPath,
		args: ["serve"],
		transport: TransportKind.stdio,
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
	};

	const client = new LanguageClient("scalimYamlDsl", "Scalim YAML DSL", serverOptions, clientOptions);
	currentClient = client;

	context.subscriptions.push(
		client.onDidChangeState((event) => {
			if (event.newState === State.Stopped && !expectedStop) {
				output.appendLine("[lsp] Server stopped unexpectedly. Use 'Scalim YAML DSL: Restart server' to recover.");
				void vscode.window.showErrorMessage(
					"Scalim YAML DSL server stopped unexpectedly.",
					"Restart server",
					"Reinstall server",
				).then((choice) => {
					if (choice === "Restart server") {
						void restartServer(context, output, /*reinstall*/ false);
					}
					if (choice === "Reinstall server") {
						void restartServer(context, output, /*reinstall*/ true);
					}
				});
			}
		}),
	);

	output.appendLine(`[lsp] Starting: ${env.scalimYamlDslLspPath} serve`);
	try {
		await client.start();
		output.appendLine("[lsp] Ready.");
	} catch (e) {
		output.appendLine("[lsp] Failed to start.");
		output.appendLine(String(e));
		void vscode.window.showErrorMessage("Scalim YAML DSL: failed to start server. Check Output > Scalim YAML DSL.");
	}
}

async function restartServer(
	context: vscode.ExtensionContext,
	output: vscode.OutputChannel,
	reinstall: boolean,
): Promise<void> {
	const run = async (): Promise<void> => {
		const { pythonPathOverride, pinnedServerSpec, autoSchemaBinding } = getExtensionConfig();

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

		const py = await detectPython(output, pythonPathOverride);
		if (!py) {
			void vscode.window.showErrorMessage(
				"Scalim YAML DSL requires Python >=3.10. Configure scalim.yamlDsl.pythonPath or install python3.",
			);
			output.appendLine("[python] No suitable python found.");
			return;
		}

		const env = await ensureVenv(context, output, py.pythonPath, pinnedServerSpec);
		currentEnv = env;

		const schemaPaths = await resolveSchemaPaths(output, env.scalimCliPath);
		env.schemaPaths = schemaPaths;

		if (autoSchemaBinding) {
			await maybeBindSchemas(output, schemaPaths);
		} else {
			output.appendLine("[schema] autoSchemaBinding=false; skipping workspace yaml.schemas update.");
		}

		await startClient(context, output, env);
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

export async function activate(context: vscode.ExtensionContext): Promise<void> {
	const output = vscode.window.createOutputChannel("Scalim YAML DSL");
	context.subscriptions.push(output);

	output.appendLine("[activate] Scalim YAML DSL extension activated.");

	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.restartServer", async () => {
			await restartServer(context, output, /*reinstall*/ false);
		}),
	);
	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.reinstallServer", async () => {
			await restartServer(context, output, /*reinstall*/ true);
		}),
	);
	context.subscriptions.push(
		vscode.commands.registerCommand("scalim.yamlDsl.showDiagnostics", async () => {
			if (!currentEnv) {
				output.appendLine("[diag] No provisioned environment yet; provisioning first.");
				await restartServer(context, output, /*reinstall*/ false);
			}
			if (!currentEnv) {
				return;
			}
			output.appendLine(
				[
					"[diag] Environment:",
					`  venvPath=${currentEnv.venvPath}`,
					`  pythonPath=${currentEnv.pythonPath}`,
					`  pythonVersion=${currentEnv.pythonVersion}`,
					`  serverVersion=${currentEnv.serverPackageVersion ?? "<unknown>"}`,
					`  pinnedServerSpec=${currentEnv.pinnedServerSpec}`,
				].join("\n"),
			);
			if (currentEnv.schemaPaths) {
				output.appendLine(`[diag] schemaPaths=${JSON.stringify(currentEnv.schemaPaths, null, 2)}`);
			}
			await dumpDiscovery(output, currentEnv);
			output.show(true);
		}),
	);

	// Best-effort auto-start. Failures should be diagnosable and must not break YAML editing.
	void restartServer(context, output, /*reinstall*/ false);
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
