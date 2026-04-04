export type YamlSchemasSetting = Record<string, string | string[]>;

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizePatterns(value: unknown): string[] | undefined {
	if (typeof value === "string") {
		return [value];
	}
	if (Array.isArray(value) && value.every((item) => typeof item === "string")) {
		return value.slice();
	}
	return undefined;
}

export function mergeYamlSchemas(existing: unknown, additions: Record<string, string[]>): YamlSchemasSetting {
	const base: Record<string, unknown> = isRecord(existing) ? existing : {};
	const merged: YamlSchemasSetting = {};

	for (const [key, value] of Object.entries(base)) {
		const patterns = normalizePatterns(value);
		if (patterns) {
			merged[key] = patterns;
		}
	}

	for (const [schema, patterns] of Object.entries(additions)) {
		const existingPatterns = normalizePatterns(merged[schema]);
		if (!existingPatterns) {
			merged[schema] = patterns.slice();
			continue;
		}

		const next = existingPatterns.slice();
		for (const pattern of patterns) {
			if (!next.includes(pattern)) {
				next.push(pattern);
			}
		}
		merged[schema] = next;
	}

	return merged;
}

