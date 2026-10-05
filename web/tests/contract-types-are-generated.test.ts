// web/tests/contract-types-are-generated.test.ts
//
// Cross-cutting test: the committed feed types are exactly what the generator produces from the
// committed JSON Schema, so they are never edited by hand and never stale.
//
// Tested:
// - The committed types match the types generated from the committed schema
// - The committed file starts with the generated-file banner
// - A changed schema produces different types
//
// What is covered:
// - Happy path (the committed file is current)
// - Error case (the check cannot pass vacuously: a schema change changes the output)
//
// Run with: cd web && pnpm exec vitest run tests/contract-types-are-generated.test.ts
//
// SEE: web/scripts/contract-types.js, web/src/lib/contract/games.ts, api/schemas/games.schema.json
// @vitest-environment node
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { bannerComment, renderTypes, schemaPath, typesPath } from '../scripts/contract-types.js';

const schema = JSON.parse(readFileSync(schemaPath, 'utf8')) as {
	properties: Record<string, unknown>;
};
const committed = readFileSync(typesPath, 'utf8');

describe('contract types', () => {
	it('matches the types generated from the committed schema', async () => {
		const generated = await renderTypes(schema);

		expect(committed, 'web/src/lib/contract/games.ts is stale: run scripts/contract.sh').toBe(
			generated
		);
	});

	it('marks the file as generated and not to be edited by hand', () => {
		expect(committed.startsWith(bannerComment)).toBe(true);
	});

	it('produces different types when the schema changes', async () => {
		const changed = {
			...schema,
			properties: { ...schema.properties, extraField: { type: 'string' } },
			required: [...(schema as { required?: string[] }).required!, 'extraField']
		};

		expect(await renderTypes(changed)).not.toBe(committed);
	});
});
