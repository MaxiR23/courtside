// web/tests/headers-first-line-offset.test.ts
//
// Cross-cutting test: the distance between the nav row and the first line of every page header is
// set by styles jsdom cannot measure, so the rules that set it are asserted in the source.
//
// Tested:
// - PageHeader applies --header-first-line-offset to the main box and the mobile token under .mobile
// - The home rule sets 0, so its copy stays centered
// - No component other than PageHeader uses either token
// - No component style reaches into the nav row with :global
// - The rule reader flags a missing rule
//
// What is covered:
// - Happy path (PageHeader applies both tokens), edge case (the home) and error case (a missing rule)
// - Pixels are not measured here: they were measured in Chromium on /preview at 1280px and 390px
//   (the header positions of every page, on main and on the branch), as in schedule-header-aligns.test.ts
//
// Run with: cd web && pnpm exec vitest run tests/headers-first-line-offset.test.ts
//
// SEE: web/src/lib/styles/tokens.css, web/src/lib/components/PageHeader.svelte, docs/design.md
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const srcDir = join(import.meta.dirname, '../src');

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

function sets(css: string, selector: string, property: string, value: string): boolean {
	return rulesOf(css).some(
		(rule) =>
			rule.selectors.includes(selector) &&
			rule.declarations.some(
				(d) => d.property === property && d.value.replace(/\s+/g, ' ') === value
			)
	);
}

const componentsDir = join(srcDir, 'lib/components');
const read = (name: string) => readFileSync(join(componentsDir, name), 'utf8');

const TOKEN = '--header-first-line-offset';
const MOBILE_TOKEN = '--header-first-line-offset-mobile';

describe('header first-line offset', () => {
	it('applies the first-line offset in PageHeader, and the mobile offset under .mobile', () => {
		const css = styleOf(read('PageHeader.svelte'));
		expect(sets(css, '.main-inner', 'padding-top', `var(${TOKEN})`)).toBe(true);
		expect(sets(css, '.mobile .main-inner', 'padding-top', `var(${MOBILE_TOKEN})`)).toBe(true);
	});

	it('keeps the home copy centered: no first-line offset', () => {
		const css = styleOf(read('PageHeader.svelte'));
		expect(sets(css, '.home .main-inner', 'padding-top', '0')).toBe(true);
	});

	it('uses neither token in any other component', () => {
		const files = readdirSync(componentsDir).filter(
			(file) => file.endsWith('.svelte') && file !== 'PageHeader.svelte'
		);
		const offenders = files.filter((file) => {
			const css = styleOf(read(file));
			return css.includes(`var(${TOKEN}`);
		});
		expect(
			offenders,
			`use the first-line offset outside PageHeader: ${offenders.join(', ')}`
		).toEqual([]);
	});

	it('reaches into the nav row from no component style', () => {
		const files = readdirSync(componentsDir).filter((file) => file.endsWith('.svelte'));
		const offenders = files.filter((file) => styleOf(read(file)).includes(':global(.nav-row)'));
		expect(offenders, `reach into the nav row: ${offenders.join(', ')}`).toEqual([]);
	});

	it('flags a missing rule', () => {
		expect(sets('.content { gap: 0; }', '.main-inner', 'padding-top', `var(${TOKEN})`)).toBe(false);
	});
});
