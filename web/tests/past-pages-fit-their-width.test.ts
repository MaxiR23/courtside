// web/tests/past-pages-fit-their-width.test.ts
//
// Cross-cutting test: the layouts of the past season pages are set by styles jsdom cannot measure, so
// the rules that set them are asserted in the component sources (ADR 0054).
//
// Tested:
// - The components to scan are found, and the scan cannot pass by finding no file
// - The standings desktop table takes the page width, so both conference tables share their columns
// - The standings team cell has an end padding, the city and name truncate with an ellipsis, and the clinch tag keeps its size
// - The playoffs bracket undecided row has one shrinkable column, so a long slot label truncates
// - The All-Star games and sections grids have one shrinkable column, so the mobile cards row scrolls inside itself
// - The page header gives its content one shrinkable column, so a long postseason mark shrinks instead of widening the page
// - The champion hero title takes its mobile size token next to the trophy
// - The standings team column takes 5fr of the desktop row, so a long full name with a clinch tag is not cut
// - The rule reader flags a missing rule
//
// What is covered:
// - Happy path (every rule is in its component), edge cases (a selector list, a pseudo-class selector) and the error case (a missing rule)
// - Pixels are not measured: that the tables fit 1320px and 390px shows no horizontal scroll is checked by eye in a browser
//
// Run with: cd web && pnpm exec vitest run tests/past-pages-fit-their-width.test.ts
//
// SEE: web/src/lib/components/GameHeader.svelte, web/src/lib/components/ChampionHero.svelte,
// web/src/lib/components/StandingsTable.svelte, web/src/lib/components/SeriesNode.svelte,
// web/src/lib/components/AllStarGames.svelte, web/src/lib/components/AllStarPage.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const componentsDir = join(import.meta.dirname, '../src/lib/components');

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

describe('the rule reader', () => {
	it('finds a rule of a selector list and of a pseudo-class selector', () => {
		const css = '.a, .b { overflow: hidden; } .t:not(.m) { width: 100%; }';
		expect(sets(css, '.b', 'overflow', 'hidden')).toBe(true);
		expect(sets(css, '.t:not(.m)', 'width', '100%')).toBe(true);
	});

	it('flags a missing rule', () => {
		expect(sets('.a { width: 50%; }', '.a', 'width', '100%')).toBe(false);
		expect(sets('', '.a', 'width', '100%')).toBe(false);
	});

	it('reads a style of each past page component, so the scan cannot pass by finding no file', () => {
		for (const name of [
			'StandingsTable.svelte',
			'SeriesNode.svelte',
			'AllStarGames.svelte',
			'AllStarPage.svelte',
			'GameHeader.svelte',
			'ChampionHero.svelte'
		]) {
			expect(rulesOf(styleFile(name)).length, name).toBeGreaterThan(0);
		}
	});
});

describe('the standings table', () => {
	const css = styleFile('StandingsTable.svelte');

	it('takes the page width on desktop, so both conferences share their columns', () => {
		expect(sets(css, '.table:not(.mobile)', 'width', '100%')).toBe(true);
		expect(sets(css, '.table:not(.mobile)', 'min-width', '0')).toBe(true);
		expect(sets(css, '.table', 'min-width', 'max-content')).toBe(true);
	});

	it('gives the team cell an end padding and truncates the city and the name', () => {
		expect(sets(css, '.cell.team', 'padding-inline-end', 'var(--game-list-gap)')).toBe(true);
		for (const selector of ['.city', '.name']) {
			expect(sets(css, selector, 'overflow', 'hidden'), selector).toBe(true);
			expect(sets(css, selector, 'text-overflow', 'ellipsis'), selector).toBe(true);
			expect(sets(css, selector, 'white-space', 'nowrap'), selector).toBe(true);
		}
		expect(sets(css, '.team-link', 'min-width', '0')).toBe(true);
	});

	it('keeps the clinch tag from shrinking', () => {
		expect(sets(css, '.clinch', 'flex', 'none')).toBe(true);
	});
});

describe('the playoffs bracket', () => {
	it('gives the undecided row one shrinkable column, so a long slot label truncates', () => {
		const css = styleFile('SeriesNode.svelte');
		expect(sets(css, '.undecided', 'grid-template-columns', 'minmax(0, 1fr)')).toBe(true);
		expect(sets(css, '.slot-label', 'white-space', 'nowrap')).toBe(true);
	});
});

describe('the All-Star page', () => {
	it('gives the games and the sections one shrinkable column', () => {
		expect(
			sets(
				styleFile('AllStarGames.svelte'),
				'.all-star-games',
				'grid-template-columns',
				'minmax(0, 1fr)'
			)
		).toBe(true);
		expect(
			sets(styleFile('AllStarPage.svelte'), '.sections', 'grid-template-columns', 'minmax(0, 1fr)')
		).toBe(true);
	});
});

describe('the game header', () => {
	it('gives its content one shrinkable column, so a long postseason mark shrinks', () => {
		const css = styleFile('PageHeader.svelte');
		expect(sets(css, '.main-inner', 'grid-template-columns', 'minmax(0, 1fr)')).toBe(true);
		expect(sets(css, '.lead', 'grid-template-columns', 'minmax(0, 1fr)')).toBe(true);
		expect(sets(css, '.lead', 'min-width', '0')).toBe(true);
	});
});

describe('the champion hero', () => {
	it('sizes the title with the mobile token next to the trophy', () => {
		expect(
			sets(
				styleFile('ChampionHero.svelte'),
				'h1.mobile',
				'font-size',
				'var(--playoffs-hero-title-size-mobile)'
			)
		).toBe(true);
	});
});

describe('the standings team column', () => {
	it('takes 5fr of the desktop row', () => {
		const row = rulesOf(styleFile('StandingsTable.svelte')).find((rule) =>
			rule.selectors.includes('.row')
		);
		const template = row?.declarations.find((d) => d.property === 'grid-template-columns');
		expect(template?.value.replace(/\s+/g, ' ')).toBe(
			'minmax(var(--standings-team-column-page-min), 5fr) repeat(14, minmax(var(--box-column-min), 1fr))'
		);
	});
});
