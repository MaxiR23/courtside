// web/scripts/contract-types.js
//
// Generates the feed TypeScript types from the committed JSON Schema.
// Run with: cd web && pnpm run contract (or scripts/contract.sh from the root)
// The options live here only: the check test imports this module.
//
// SEE: api/schemas/games.schema.json, web/src/lib/contract/games.ts,
// api/schemas/game-detail.schema.json, web/src/lib/contract/game-detail.ts,
// api/schemas/player.schema.json, web/src/lib/contract/player.ts,
// api/schemas/team.schema.json, web/src/lib/contract/team.ts
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compile } from 'json-schema-to-typescript';
import { createRequire } from 'node:module';
import prettierConfig from '../prettier.config.js';

// Loaded through require so Vitest's browser resolution cannot swap in the browser build.
const { format } = createRequire(import.meta.url)('prettier');

export const feeds = [
	{ name: 'games', rootName: 'GamesFeed' },
	{ name: 'game-detail', rootName: 'GameDetailFeed' },
	{ name: 'player', rootName: 'PlayerFeed' },
	{ name: 'team', rootName: 'TeamFeed' }
].map((feed) => ({
	...feed,
	schemaPath: join(import.meta.dirname, `../../api/schemas/${feed.name}.schema.json`),
	typesPath: join(import.meta.dirname, `../src/lib/contract/${feed.name}.ts`)
}));

/**
 * @param {{ name: string }} feed
 * @returns {string} the generated-file banner of the feed's types
 */
export function bannerComment(feed) {
	return [
		'/**',
		` * Generated from api/schemas/${feed.name}.schema.json by scripts/contract.sh.`,
		' * Do not edit by hand: run scripts/contract.sh instead.',
		' */'
	].join('\n');
}

/**
 * @param {object} schema JSON Schema of the feed
 * @param {{ name: string, rootName: string, typesPath: string }} feed
 * @returns {Promise<string>} formatted TypeScript source
 */
export async function renderTypes(schema, feed) {
	const output = await compile(/** @type {any} */ (schema), feed.rootName, {
		bannerComment: bannerComment(feed),
		format: false,
		additionalProperties: false
	});
	return format(output, { ...prettierConfig, filepath: feed.typesPath });
}

export async function writeTypes() {
	for (const feed of feeds) {
		const schema = JSON.parse(await readFile(feed.schemaPath, 'utf8'));
		await mkdir(dirname(feed.typesPath), { recursive: true });
		await writeFile(feed.typesPath, await renderTypes(schema, feed));
	}
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
	await writeTypes();
}
