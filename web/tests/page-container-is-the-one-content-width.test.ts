// web/tests/page-container-is-the-one-content-width.test.ts
//
// Cross-cutting test: the page content width and side padding live in PageContainer, so no other
// component or route sets the content width on its own rule.
//
// Tested:
// - The components and routes to scan are found, and the scan cannot pass by finding no file
// - The matcher flags a rule that sets the content width, and passes other widths and comments
// - PageContainer sets the content width
// - PageHeader sets it too, so the exception never keeps a stale entry
// - No other component or route sets it
// - The anchored sections keep a scroll margin above the container padding
//
// What is covered:
// - Happy path (only PageContainer and PageHeader set it), edge cases (a selector list,
//   a comment) and the error case (a rule that sets it is flagged)
// - The preview route is left out: it is a component catalog, not a page
//
// Run with: cd web && pnpm exec vitest run tests/page-container-is-the-one-content-width.test.ts
//
// SEE: web/src/lib/components/PageContainer.svelte
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

/** Whether any rule of the CSS sets the content width. */
function setsContentWidth(css: string): boolean {
	return rulesOf(css).some((rule) =>
		rule.declarations.some(
			(d) => d.property === 'max-width' && d.value === 'var(--content-max-width)'
		)
	);
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

const allowed = new Set([
	join(componentsDir, 'PageContainer.svelte'),
	join(componentsDir, 'PageHeader.svelte')
]);

describe('the scan', () => {
	it('finds the components and routes to check', () => {
		expect(componentFiles.length).toBeGreaterThanOrEqual(100);
		expect(routeFiles.some((file) => file.endsWith('+page.svelte'))).toBe(true);
	});
});

describe('the matcher', () => {
	it('flags a rule that sets the content width, and passes other widths and comments', () => {
		expect(setsContentWidth('.a { max-width: var(--content-max-width); }')).toBe(true);
		expect(setsContentWidth('.a, .b { margin: 0; max-width: var(--content-max-width); }')).toBe(
			true
		);
		expect(setsContentWidth('.a { max-width: var(--playoffs-series-max-width); }')).toBe(false);
		expect(
			setsContentWidth(
				styleOf('<style>/* max-width: var(--content-max-width); */ .a { x: y; }</style>')
			)
		).toBe(false);
	});
});

describe('the page container', () => {
	it('sets the content width in PageContainer', () => {
		const source = readFileSync(join(componentsDir, 'PageContainer.svelte'), 'utf8');
		expect(setsContentWidth(styleOf(source))).toBe(true);
	});

	it('sets the content width in PageHeader', () => {
		const source = readFileSync(join(componentsDir, 'PageHeader.svelte'), 'utf8');
		expect(setsContentWidth(styleOf(source))).toBe(true);
	});

	it('is the only place besides PageHeader that sets the content width', () => {
		const offenders = [...componentFiles, ...routeFiles]
			.filter((file) => !allowed.has(file))
			.filter((file) => setsContentWidth(styleOf(readFileSync(file, 'utf8'))))
			.map((file) => relative(srcDir, file));
		expect(
			offenders,
			`set the content width outside PageContainer: ${offenders.join(', ')}`
		).toEqual([]);
	});

	it('gives the anchored sections a scroll margin above the container padding', () => {
		const sources = [
			[join(componentsDir, 'Schedule.svelte'), '.schedule'],
			[join(componentsDir, 'ScheduleSkeleton.svelte'), '.schedule-skeleton'],
			[join(routesDir, '+page.svelte'), '.unavailable']
		] as const;
		for (const [file, selector] of sources) {
			const has = rulesOf(styleOf(readFileSync(file, 'utf8'))).some(
				(rule) =>
					rule.selectors.includes(selector) &&
					rule.declarations.some(
						(d) => d.property === 'scroll-margin-top' && d.value === 'var(--side-padding)'
					)
			);
			expect(has, `${relative(srcDir, file)} ${selector}`).toBe(true);
		}
	});
});
