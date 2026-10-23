// web/tests/playoffs-bracket-without-a-camera.test.ts
//
// Cross-cutting test: the playoffs bracket is a plain grid at 1:1, with no camera (ADR 0071).
//
// Tested:
// - No playoffs bracket piece (PlayoffBracket, SeriesNode, SeriesSheet, SeriesGameLine, PlayInStrip,
//   PlayoffsPage, the playoffs folder) imports the shared camera under #lib/bracket/
// - No rule of PlayoffBracket or SeriesNode declares transform, scale, translate or rotate
// - The map takes its columns from the token, the tree is an 8-column grid of shrinkable tracks and
//   the cards are spread with space-around
// - The Cup still draws its bracket with the camera
//
// What is covered:
// - The sources of the components and the playoffs folder, read as text; jsdom measures no layout
// - The scan cannot pass vacuously: each style read has rules, and the rule reader finds and misses rules
//
// Run with: cd web && pnpm exec vitest run tests/playoffs-bracket-without-a-camera.test.ts
//
// SEE: web/src/lib/components/PlayoffBracket.svelte, web/src/lib/components/SeriesNode.svelte,
// web/src/lib/playoffs, web/src/lib/cup/camera.svelte.ts
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const srcDir = join(import.meta.dirname, '../src/lib');
const componentsDir = join(srcDir, 'components');
const playoffsDir = join(srcDir, 'playoffs');

type Declaration = { property: string; value: string };
type Rule = { selectors: string[]; declarations: Declaration[] };

function styleOf(source: string): string {
	const match = source.match(/<style[^>]*>([\s\S]*?)<\/style>/);
	return (match?.[1] ?? '').replace(/\/\*[\s\S]*?\*\//g, '');
}

function rulesOf(style: string): Rule[] {
	const rules: Rule[] = [];
	for (const match of style.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
		const declarations = (match[2] ?? '')
			.split(';')
			.map((part) => part.trim())
			.filter((part) => part.includes(':'))
			.map((part) => {
				const index = part.indexOf(':');
				return {
					property: part.slice(0, index).trim().toLowerCase(),
					value: part.slice(index + 1).trim()
				};
			});
		const selectors = (match[1] ?? '').split(',').map((selector) => selector.trim());
		rules.push({ selectors, declarations });
	}
	return rules;
}

/** Whether a rule for the selector sets the property to the value. */
function sets(css: string, selector: string, property: string, value: string): boolean {
	return rulesOf(css).some(
		(rule) =>
			rule.selectors.includes(selector) &&
			rule.declarations.some((d) => d.property === property && d.value === value)
	);
}

const styleFile = (name: string): string =>
	styleOf(readFileSync(join(componentsDir, name), 'utf8'));

const BRACKET_PIECES = [
	'PlayoffBracket.svelte',
	'SeriesNode.svelte',
	'SeriesSheet.svelte',
	'SeriesGameLine.svelte',
	'PlayInStrip.svelte',
	'PlayoffsPage.svelte'
];

const playoffsSources = readdirSync(playoffsDir).map((name) => ({
	name: `playoffs/${name}`,
	source: readFileSync(join(playoffsDir, name), 'utf8')
}));

const pieceSources = BRACKET_PIECES.map((name) => ({
	name,
	source: readFileSync(join(componentsDir, name), 'utf8')
}));

describe('the rule reader', () => {
	it('finds a declared rule and misses an absent one', () => {
		const css = '.a, .b { transform: none; } .c { width: 1px; }';
		expect(sets(css, '.b', 'transform', 'none')).toBe(true);
		expect(sets(css, '.c', 'transform', 'none')).toBe(false);
		expect(sets('', '.a', 'transform', 'none')).toBe(false);
	});

	it('reads a style of each bracket piece, so the scan cannot pass by finding no file', () => {
		expect(playoffsSources.length).toBeGreaterThanOrEqual(5);
		for (const name of BRACKET_PIECES) {
			expect(rulesOf(styleFile(name)).length, name).toBeGreaterThan(0);
		}
	});
});

describe('the playoffs bracket', () => {
	it('imports nothing from the shared camera under #lib/bracket/', () => {
		for (const { name, source } of [...pieceSources, ...playoffsSources]) {
			expect(source, name).not.toMatch(/#lib\/bracket\//);
			expect(source, name).not.toMatch(/bracket-camera/);
		}
	});

	it('declares no transform, scale, translate or rotate in the bracket and its cards', () => {
		for (const name of ['PlayoffBracket.svelte', 'SeriesNode.svelte']) {
			const properties = rulesOf(styleFile(name)).flatMap((rule) =>
				rule.declarations.map((d) => d.property)
			);
			expect(properties.length, name).toBeGreaterThan(0);
			for (const forbidden of ['transform', 'scale', 'translate', 'rotate']) {
				expect(properties, `${name} declares ${forbidden}`).not.toContain(forbidden);
			}
		}
	});

	it('takes the map columns from the token and spreads the cards with space-around', () => {
		const css = styleFile('PlayoffBracket.svelte');
		expect(sets(css, '.map', 'grid-template-columns', 'var(--playoffs-bracket-columns)')).toBe(
			true
		);
		expect(sets(css, '.cards', 'justify-content', 'space-around')).toBe(true);
	});

	it('draws the tree as an 8-column grid of shrinkable tracks', () => {
		const css = styleFile('PlayoffBracket.svelte');
		expect(sets(css, '.grid', 'grid-template-columns', 'repeat(8, minmax(0, 1fr))')).toBe(true);
	});
});

describe('the Cup bracket', () => {
	it('still draws with the shared camera', () => {
		const camera = readFileSync(join(srcDir, 'cup/camera.svelte.ts'), 'utf8');
		expect(camera).toMatch(/from '#lib\/bracket\/layer\.ts'/);
	});
});
