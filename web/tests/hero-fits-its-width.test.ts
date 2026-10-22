// web/tests/hero-fits-its-width.test.ts
//
// Cross-cutting test: the layout of the home hero is set by styles jsdom cannot measure, so the rule
// that sets it and the token values it uses are asserted in the sources.
//
// Tested:
// - The hero columns are an auto-fit grid with a minimum column width token
// - From the token values, two columns fit the desktop content width and three never do
// - From the token values, the columns collapse to one at 390px
// - The rule reader flags a missing rule
//
// What is covered:
// - Happy path (the rule is in the component) and the error case (a missing rule)
// - Pixels are not measured: that the hero looks right at 1440px and 390px is checked by eye in a browser
//
// Run with: cd web && pnpm exec vitest run tests/hero-fits-its-width.test.ts
//
// SEE: web/src/lib/components/Hero.svelte, web/src/lib/styles/tokens.css
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

/** The pixel value of a token declared as a plain length. */
function px(tokens: string, name: string): number {
	const match = tokens.match(new RegExp(`${name}:\\s*(\\d+)px;`));
	if (!match) throw new Error(`No pixel token ${name}`);
	return Number(match[1]);
}

/** The clamp(min, preferred, max) bounds of a token, in pixels. */
function clampBounds(tokens: string, name: string): [number, number] {
	const match = tokens.match(new RegExp(`${name}:\\s*clamp\\((\\d+)px,[^,]+,\\s*(\\d+)px\\);`));
	if (!match) throw new Error(`No clamp token ${name}`);
	return [Number(match[1]), Number(match[2])];
}

const hero = styleOf(readFileSync(join(srcDir, 'lib/components/Hero.svelte'), 'utf8'));
const tokens = readFileSync(join(srcDir, 'lib/styles/tokens.css'), 'utf8');

describe('the rule reader', () => {
	it('flags a missing rule', () => {
		expect(sets('.a { width: 50%; }', '.a', 'width', '100%')).toBe(false);
		expect(sets('', '.a', 'width', '100%')).toBe(false);
	});

	it('finds a rule of a selector list', () => {
		expect(sets('.a, .b { width: 100%; }', '.b', 'width', '100%')).toBe(true);
	});
});

describe('the hero columns', () => {
	it('are an auto-fit grid with a minimum column width', () => {
		expect(
			sets(
				hero,
				'.columns',
				'grid-template-columns',
				'repeat(auto-fit, minmax(min(100%, var(--hero-column-min)), 1fr))'
			)
		).toBe(true);
	});

	it('hold two columns at the desktop width and never three', () => {
		const column = px(tokens, '--hero-column-min');
		const content = px(tokens, '--content-max-width');
		const [minGap, maxGap] = clampBounds(tokens, '--hero-gap');
		expect(2 * column + maxGap).toBeLessThanOrEqual(content);
		expect(3 * column + 2 * minGap).toBeGreaterThan(content);
	});

	it('collapse to one column at 390px', () => {
		const column = px(tokens, '--hero-column-min');
		const [minSide] = clampBounds(tokens, '--side-padding');
		expect(390 - 2 * minSide).toBeLessThan(column);
	});
});
