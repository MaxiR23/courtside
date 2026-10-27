// web/tests/schedule-header-aligns.test.ts
//
// Cross-cutting test: the alignment of the schedule header's count and freshness label is set by
// styles jsdom cannot measure, so the rules that set it are asserted in the source.
//
// Tested:
// - .meta right-aligns its rows (the desktop header is unchanged)
// - .mobile .meta left-aligns them, and the header binds the mobile class to the narrow viewport and to the header wrapping
// - The rule reader flags a missing rule
//
// What is covered:
// - Happy path (the rules are in the component) and the error case (a missing rule)
// - Pixels are not measured here: they were measured once in Chromium at 390px and 1280px
//
// Run with: cd web && pnpm exec vitest run tests/schedule-header-aligns.test.ts
//
// SEE: web/src/lib/components/Schedule.svelte
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

const schedule = readFileSync(join(srcDir, 'lib/components/Schedule.svelte'), 'utf8');

describe('schedule header alignment', () => {
	it('right-aligns the meta rows by default', () => {
		expect(sets(styleOf(schedule), '.meta', 'justify-items', 'end')).toBe(true);
	});

	it('left-aligns the meta rows under the mobile class', () => {
		expect(sets(styleOf(schedule), '.mobile .meta', 'justify-items', 'start')).toBe(true);
	});

	it('binds the mobile class on the header to the narrow viewport and the wrap and the wrap', () => {
		expect(schedule).toContain('class:mobile={!wide.current && wrapped}');
	});

	it('flags a missing rule', () => {
		expect(sets('.meta { display: grid; }', '.mobile .meta', 'justify-items', 'start')).toBe(false);
	});
});
