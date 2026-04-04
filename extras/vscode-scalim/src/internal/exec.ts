import * as cp from "node:child_process";

export type ExecResult = {
	stdout: string;
	stderr: string;
	exitCode: number;
};

export async function runCommand(
	executable: string,
	args: readonly string[],
	options: cp.ExecFileOptions = {},
): Promise<ExecResult> {
	return await new Promise<ExecResult>((resolve, reject) => {
		cp.execFile(
			executable,
			[...args],
			{
				...options,
				encoding: "utf8",
				maxBuffer: 10 * 1024 * 1024,
			},
			(error, stdout, stderr) => {
				if (!error) {
					resolve({
						stdout: stdout ?? "",
						stderr: stderr ?? "",
						exitCode: 0,
					});
					return;
				}

				const execError = error as cp.ExecFileException;
				const exitCode = typeof execError.code === "number" ? execError.code : 127;
				const stderrText = (stderr ?? "").trim() || execError.message || "";

				resolve({
					stdout: stdout ?? "",
					stderr: stderrText,
					exitCode,
				});
			},
		);
	});
}
