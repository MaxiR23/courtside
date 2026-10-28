// web/tests/headers-first-line-offset.test.ts
//
// Cross-cutting test: the distance between the nav row and the first line of every page header on
// mobile is set by styles jsdom cannot measure, so the rules that set it are asserted in the source.
//
// Tested:
// - Every listed header applies --header-first-line-offset-mobile on mobile
// - The Playoffs hero drops the padding under the nav on mobile
// - The six headers that gain the mobile class bind it to the mobile layout
// - The token is used only under the mobile class, and the home hero does not use it
// - The rule reader flags a missing rule
//
// What is covered:
// - Happy path (every header applies the token), edge case (the token is used only under .mobile)
//   and error case (a missing rule)
// - Pixels are not measured here: they were measured once in Chromium at 390px, as in
//   schedule-header-aligns.test.ts
//
// Run with: cd web && pnpm exec vitest run tests/headers-first-line-offset.test.ts
//
// SEE: web/src/lib/styles/tokens.css, docs/design.md
import { readFileSync } from 'node:fs';
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

const read = (name: string) => readFileSync(join(srcDir, 'lib/components', name), 'utf8');

const TOKEN = '--header-first-line-offset-mobile';
const GRID_GAP = `calc(var(${TOKEN}) - var(--panel-section-gap))`;
const GRID_SELECTOR = '.mobile .content:has(> .first-line) > :global(.nav-row)';
const CUP_GAP = `calc(var(${TOKEN}) - var(--cup-header-gap))`;

const GRID_HEADERS = [
	'StandingsHeader.svelte',
	'TeamHeader.svelte',
	'PlayerHeader.svelte',
	'DayHeader.svelte',
	'GameHeader.svelte',
	'PlayoffsHeader.svelte'
];
const ALL_HEADERS = [
	...GRID_HEADERS,
	'CupHeader.svelte',
	'ChampionHero.svelte',
	'AllStarHeader.svelte'
];

describe('header first-line offset', () => {
	it('applies the header first-line offset on mobile in every listed header', () => {
		const cases: [string, string, string, string][] = [
			...GRID_HEADERS.map((file): [string, string, string, string] => [
				file,
				GRID_SELECTOR,
				'margin-bottom',
				GRID_GAP
			]),
			['CupHeader.svelte', '.mobile .first-line', 'margin-top', CUP_GAP],
			['ChampionHero.svelte', '.mobile .inner', 'padding-top', `var(${TOKEN})`],
			['AllStarHeader.svelte', '.mobile .content', 'padding-top', `var(${TOKEN})`],
			['PlayoffsHeader.svelte', '.mobile .above-hero', 'padding-bottom', '0']
		];
		for (const [file, selector, property, value] of cases) {
			expect(sets(styleOf(read(file)), selector, property, value), `${file} ${selector}`).toBe(
				true
			);
		}
	});

	it('binds the mobile class to the mobile layout on every header', () => {
		for (const file of GRID_HEADERS) {
			expect(read(file), file).toContain("class:mobile={layout === 'mobile'}");
		}
	});

	it('uses the token only under the mobile class', () => {
		for (const file of ALL_HEADERS) {
			const used = rulesOf(styleOf(read(file))).filter((rule) =>
				rule.declarations.some((d) => d.value.includes(TOKEN))
			);
			expect(used.length, file).toBeGreaterThan(0);
			for (const rule of used) {
				for (const selector of rule.selectors) {
					expect(selector.startsWith('.mobile'), `${file} ${selector}`).toBe(true);
				}
			}
		}
	});

	it('keeps the home hero without the token', () => {
		expect(read('Hero.svelte')).not.toContain(TOKEN);
	});

	it('flags a missing rule', () => {
		expect(sets('.content { gap: 0; }', GRID_SELECTOR, 'margin-bottom', GRID_GAP)).toBe(false);
	});
});
