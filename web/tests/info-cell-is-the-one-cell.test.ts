// web/tests/info-cell-is-the-one-cell.test.ts
//
// Cross-cutting test: the info cell (label, big value and muted sub line under a divider) lives in
// InfoCell, so no other component or route writes its divider declarations or its value
// declarations on its own rule.
//
// Tested:
// - The components and routes to scan are found, and the scan cannot pass by finding no file
// - The matcher flags a rule with the whole set, and passes partial sets, split sets and comments
// - InfoCell holds the divider set and the value set, and draws its label through Kicker
// - No other component or route holds the divider set
// - No other component or route holds the value set, except the listed lookalikes
// - Every listed lookalike still holds the value set, so the list never keeps a stale entry
//
// What is covered:
// - Happy path (only InfoCell holds the sets), edge cases (a selector list, a media query, a split
//   set, a comment) and the error case (a rule that holds a set is flagged)
//
// Run with: cd web && pnpm exec vitest run tests/info-cell-is-the-one-cell.test.ts
//
// SEE: web/src/lib/components/InfoCell.svelte
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const srcDir = join(import.meta.dirname, '../src');
const routesDir = join(srcDir, 'routes');
const componentsDir = join(srcDir, 'lib/components');

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

const DIVIDER_SET: Declaration[] = [
	{ property: 'padding-top', value: 'var(--game-list-gap)' },
	{ property: 'border-top', value: 'var(--hairline) solid var(--color-divider)' }
];

const VALUE_SET: Declaration[] = [
	{ property: 'font-family', value: 'var(--font-heading)' },
	{ property: 'font-size', value: 'var(--detail-info-value-size)' }
];

/** The selectors (joined with ', ') of every rule that holds the whole set. */
function rulesHolding(css: string, set: Declaration[]): string[] {
	return rulesOf(css)
		.filter((rule) =>
			set.every((want) =>
				rule.declarations.some((d) => d.property === want.property && d.value === want.value)
			)
		)
		.map((rule) => rule.selectors.join(', '));
}

function svelteFilesUnder(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) return svelteFilesUnder(path);
		return entry.name.endsWith('.svelte') ? [path] : [];
	});
}

const componentFiles = svelteFilesUnder(componentsDir);
const routeFiles = svelteFilesUnder(routesDir);
const infoCellFile = join(componentsDir, 'InfoCell.svelte');

// Same type as the info cell value, not an info cell. File name (in lib/components) to selectors.
const valueLookalikes: Record<string, string[]> = {
	'GameHeader.svelte': ['.arena', '.cell-value'], // photo caption; the venue cell has no divider and is centered beside the photo
	'TeamOverview.svelte': ['.arena'], // photo caption
	'NextGameCard.svelte': ['.opponent'], // the opponent line of the card
	'SeasonSeries.svelte': ['.result'] // the series result
};

function styleFor(file: string): string {
	return styleOf(readFileSync(file, 'utf8'));
}

describe('the scan', () => {
	it('finds the components and routes to check', () => {
		expect(componentFiles.length).toBeGreaterThanOrEqual(100);
		expect(routeFiles.some((file) => file.endsWith('+page.svelte'))).toBe(true);
	});
});

describe('the matcher', () => {
	const set =
		'padding-top: var(--game-list-gap); border-top: var(--hairline) solid var(--color-divider);';

	it('flags a rule with the whole set', () => {
		expect(rulesHolding(`.a { ${set} }`, DIVIDER_SET)).toEqual(['.a']);
		expect(rulesHolding(`.a { ${set} color: red; }`, DIVIDER_SET)).toEqual(['.a']);
		expect(rulesHolding(`.a, .b { ${set} }`, DIVIDER_SET)).toEqual(['.a, .b']);
		expect(rulesHolding(`@media (min-width: 40rem) { .a { ${set} } }`, DIVIDER_SET)).toEqual([
			'.a'
		]);
	});

	it('passes a partial set, a split set and a comment', () => {
		expect(rulesHolding('.a { padding-top: var(--game-list-gap); }', DIVIDER_SET)).toEqual([]);
		expect(
			rulesHolding(
				'.a { padding-top: var(--game-list-gap); } .a { border-top: var(--hairline) solid var(--color-divider); }',
				DIVIDER_SET
			)
		).toEqual([]);
		expect(rulesHolding(styleOf(`<style>/* ${set} */ .a { x: y; }</style>`), DIVIDER_SET)).toEqual(
			[]
		);
	});
});

describe('the info cell', () => {
	it('holds the divider set on .cell and the value set on .value', () => {
		const style = styleFor(infoCellFile);
		expect(rulesHolding(style, DIVIDER_SET)).toEqual(['.cell']);
		expect(rulesHolding(style, VALUE_SET)).toEqual(['.value']);
	});

	it('draws its label through Kicker', () => {
		const source = readFileSync(infoCellFile, 'utf8');
		expect(styleFor(infoCellFile)).not.toContain('var(--label-size)');
		expect(source).toContain('<Kicker');
	});

	it('is the only component or route that holds the divider set', () => {
		const offenders: string[] = [];
		for (const file of [...componentFiles, ...routeFiles]) {
			if (file === infoCellFile) continue;
			for (const selector of rulesHolding(styleFor(file), DIVIDER_SET)) {
				offenders.push(`${relative(srcDir, file)} ${selector}`);
			}
		}
		expect(offenders, `hold the divider set outside InfoCell:\n${offenders.join('\n')}`).toEqual(
			[]
		);
	});

	it('every listed lookalike still holds the value set, so the list never keeps a stale entry', () => {
		const stale: string[] = [];
		for (const [name, selectors] of Object.entries(valueLookalikes)) {
			const found = rulesHolding(styleFor(join(componentsDir, name)), VALUE_SET);
			for (const selector of selectors) {
				if (!found.includes(selector)) stale.push(`${name} ${selector}`);
			}
		}
		expect(stale, `no longer hold the value set, drop from the list: ${stale.join(', ')}`).toEqual(
			[]
		);
	});

	it('is the only place besides the listed lookalikes that holds the value set', () => {
		const offenders: string[] = [];
		for (const file of [...componentFiles, ...routeFiles]) {
			if (file === infoCellFile) continue;
			const allowed = file.startsWith(componentsDir)
				? (valueLookalikes[relative(componentsDir, file)] ?? [])
				: [];
			for (const selector of rulesHolding(styleFor(file), VALUE_SET)) {
				if (!allowed.includes(selector)) offenders.push(`${relative(srcDir, file)} ${selector}`);
			}
		}
		expect(offenders, `hold the value set outside InfoCell:\n${offenders.join('\n')}`).toEqual([]);
	});
});
