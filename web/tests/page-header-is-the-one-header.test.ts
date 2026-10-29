// web/tests/page-header-is-the-one-header.test.ts
//
// Cross-cutting test: the page header (the grid background, the nav row and the season selector)
// lives in PageHeader, so no other component or route imports the nav row or draws the header grid
// on its own, and only the calendar sheet imports the selector besides it.
//
// Tested:
// - The components and routes to scan are found, and the scan cannot pass by finding no file
// - The import matcher flags a plain, a relative and an aliased import, and passes a comment and a
//   type-only mention
// - The grid matcher flags a rule whose background image holds the grid line color, and passes
//   another gradient and a comment
// - NavRow is imported only by PageHeader
// - SeasonSelect is imported only by PageHeader and CalendarSheet
// - PageHeader draws the grid
// - Every listed non-header grid still exists, so the list never keeps a stale entry
// - No other component or route draws a grid
//
// What is covered:
// - Happy path (only PageHeader imports and draws), edge cases (aliases, relative paths, comments,
//   selector lists) and the error case (a stray import or grid is flagged)
// - The preview route is left out: it is a component catalog, not a page
//
// Run with: cd web && pnpm exec vitest run tests/page-header-is-the-one-header.test.ts
//
// SEE: web/src/lib/components/PageHeader.svelte, docs/adr/0083-one-page-header-for-every-page.md
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

function scriptOf(source: string): string {
	const match = source.match(/<script[^>]*>([\s\S]*?)<\/script>/);
	return (match?.[1] ?? '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
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

/** Whether the script imports the component (any name, any path ending in its file name). */
function importsComponent(script: string, component: string): boolean {
	return new RegExp(
		`^\\s*import\\s+\\w+\\s+from\\s+['"][^'"]*\\b${component}\\.svelte['"]`,
		'm'
	).test(script);
}

/** The selectors (joined with ', ') of every rule that draws the grid lines. */
function gridRules(css: string): string[] {
	return rulesOf(css)
		.filter((rule) =>
			rule.declarations.some(
				(d) => d.property === 'background-image' && d.value.includes('var(--color-grid-line)')
			)
		)
		.map((rule) => rule.selectors.join(', '));
}

function svelteFilesUnder(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) return entry.name === 'preview' ? [] : svelteFilesUnder(path);
		return entry.name.endsWith('.svelte') ? [path] : [];
	});
}

const componentFiles = svelteFilesUnder(componentsDir);
const routeFiles = svelteFilesUnder(routesDir);
const scanned = [...componentFiles, ...routeFiles];
const sourceOf = (file: string) => readFileSync(file, 'utf8');
const name = (file: string) => relative(srcDir, file);
const pageHeader = join(componentsDir, 'PageHeader.svelte');

// These draw a grid and are not page headers. File name (in lib/components) to the rule's selectors.
const otherGrids: Record<string, string> = {
	'AllStarGames.svelte': '.placeholder', // the video placeholder
	'AllStarPlate.svelte': '.plate.live, .live-block', // the live plate
	'GameHeader.svelte': '.bare-grid' // the venue photo placeholder
};

describe('the scan', () => {
	it('finds the components and routes to check', () => {
		expect(componentFiles.length).toBeGreaterThanOrEqual(100);
		expect(routeFiles.some((file) => file.endsWith('+page.svelte'))).toBe(true);
	});
});

describe('the matchers', () => {
	it('flags a plain, a relative and an aliased import, and passes a comment and a type mention', () => {
		expect(importsComponent("import NavRow from '#lib/components/NavRow.svelte';", 'NavRow')).toBe(
			true
		);
		expect(importsComponent("import NavRow from './NavRow.svelte';", 'NavRow')).toBe(true);
		expect(importsComponent("import Row from '../components/NavRow.svelte';", 'NavRow')).toBe(true);
		expect(
			importsComponent(
				scriptOf("<script>// import NavRow from './NavRow.svelte';\n</script>"),
				'NavRow'
			)
		).toBe(false);
		expect(
			importsComponent(
				scriptOf("<script>/* import NavRow from './NavRow.svelte'; */\n</script>"),
				'NavRow'
			)
		).toBe(false);
		expect(
			importsComponent("import type { SeasonControl } from '#lib/season/types.ts';", 'SeasonSelect')
		).toBe(false);
		expect(importsComponent("import NavRowTitle from './NavRowTitle.svelte';", 'NavRow')).toBe(
			false
		);
	});

	it('flags a rule whose background image holds the grid line color, and passes the rest', () => {
		const grid = 'background-image: linear-gradient(var(--color-grid-line) 1px, transparent 1px);';
		expect(gridRules(`.a { ${grid} }`)).toEqual(['.a']);
		expect(gridRules(`.a, .b { ${grid} }`)).toEqual(['.a, .b']);
		expect(gridRules('.a { background-image: linear-gradient(red, blue); }')).toEqual([]);
		expect(gridRules(styleOf(`<style>/* .a { ${grid} } */ .b { x: y; }</style>`))).toEqual([]);
	});
});

describe('the page header', () => {
	it('draws the grid in PageHeader', () => {
		expect(gridRules(styleOf(sourceOf(pageHeader)))).toEqual(['.grid-bg']);
	});

	it('is the only component that imports NavRow', () => {
		const offenders = scanned
			.filter((file) => file !== pageHeader)
			.filter((file) => importsComponent(scriptOf(sourceOf(file)), 'NavRow'))
			.map(name);
		expect(offenders, `import NavRow outside PageHeader: ${offenders.join(', ')}`).toEqual([]);
		expect(importsComponent(scriptOf(sourceOf(pageHeader)), 'NavRow')).toBe(true);
	});

	it('is the only page component besides the calendar sheet that imports SeasonSelect', () => {
		const allowed = new Set([pageHeader, join(componentsDir, 'CalendarSheet.svelte')]);
		const offenders = scanned
			.filter((file) => !allowed.has(file))
			.filter((file) => importsComponent(scriptOf(sourceOf(file)), 'SeasonSelect'))
			.map(name);
		expect(offenders, `import SeasonSelect outside PageHeader: ${offenders.join(', ')}`).toEqual(
			[]
		);
		for (const file of allowed) {
			expect(importsComponent(scriptOf(sourceOf(file)), 'SeasonSelect'), name(file)).toBe(true);
		}
	});

	it('keeps every listed grid that is not a page header, so the list is never stale', () => {
		const stale = Object.entries(otherGrids)
			.filter(
				([file, selector]) =>
					!gridRules(styleOf(sourceOf(join(componentsDir, file)))).includes(selector)
			)
			.map(([file]) => file);
		expect(stale, `no longer draw their grid, drop from the list: ${stale.join(', ')}`).toEqual([]);
	});

	it('is the only place besides the listed non-headers that draws a grid', () => {
		const listed = new Set(Object.keys(otherGrids).map((file) => join(componentsDir, file)));
		const offenders = scanned
			.filter((file) => file !== pageHeader && !listed.has(file))
			.filter((file) => gridRules(styleOf(sourceOf(file))).length > 0)
			.map(name);
		expect(offenders, `draw a grid outside PageHeader: ${offenders.join(', ')}`).toEqual([]);
		for (const [file, selector] of Object.entries(otherGrids)) {
			const rules = gridRules(styleOf(sourceOf(join(componentsDir, file))));
			expect(rules, file).toEqual([selector]);
		}
	});
});
