// web/scripts/contract-types.js
//
// Generates the feed TypeScript types from the committed JSON Schema.
// Run with: cd web && pnpm run contract (or scripts/contract.sh from the root)
// The options live here only: the check test imports this module.
//
// SEE: api/schemas/games.schema.json, web/src/lib/contract/games.ts
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compile } from 'json-schema-to-typescript';
import { createRequire } from 'node:module';
import prettierConfig from '../prettier.config.js';

// Loaded through require so Vitest's browser resolution cannot swap in the browser build.
const { format } = createRequire(import.meta.url)('prettier');

export const schemaPath = join(import.meta.dirname, '../../api/schemas/games.schema.json');
export const typesPath = join(import.meta.dirname, '../src/lib/contract/games.ts');

export const bannerComment = [
	'/**',
	' * Generated from api/schemas/games.schema.json by scripts/contract.sh.',
	' * Do not edit by hand: run scripts/contract.sh instead.',
	' */'
].join('\n');

/**
 * @param {object} schema JSON Schema of the feed
 * @returns {Promise<string>} formatted TypeScript source
 */
export async function renderTypes(schema) {
	const output = await compile(/** @type {any} */ (schema), 'GamesFeed', {
		bannerComment,
		format: false,
		additionalProperties: false
	});
	return format(output, { ...prettierConfig, filepath: typesPath });
}

export async function writeTypes() {
	const schema = JSON.parse(await readFile(schemaPath, 'utf8'));
	await mkdir(dirname(typesPath), { recursive: true });
	await writeFile(typesPath, await renderTypes(schema));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
	await writeTypes();
}
