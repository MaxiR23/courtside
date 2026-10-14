// web/tests/all-star-cards-fit-their-frames.test.ts
//
// Cross-cutting test: All-Star boxes that fill their parent never grow past it.
//
// Tested:
// - The All-Star components under web/src/lib/components are found
// - The rule check flags height 100% with a padding and no border-box, and passes the other cases
// - No All-Star rule sets height 100% with a non-zero padding without border-box sizing
//
// What is covered:
// - Happy path (every All-Star style passes)
// - Edge cases (zero padding, no padding, border-box present; the scan cannot pass by finding no component)
// - Error case (a rule with height 100%, a padding and no border-box is flagged)
//
// Run with: cd web && pnpm exec vitest run tests/all-star-cards-fit-their-frames.test.ts
//
// SEE: web/src/lib/components/AllStarLastTime.svelte, web/src/lib/components/AllStarMvp.svelte
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const componentsDir = join(import.meta.dirname, '../src/lib/components');
const files = readdirSync(componentsDir).filter((f) => /^AllStar.*\.svelte$/.test(f));

type Declaration = { property: string; value: string };
type Rule = { selector: string; declarations: Declaration[] };

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
		rules.push({ selector: (match[1] ?? '').trim(), declarations });
	}
	return rules;
}

function overflowsParent(declarations: Declaration[]): boolean {
	const fillsHeight = declarations.some((d) => d.property === 'height' && d.value === '100%');
	const padded = declarations.some(
		(d) =>
			(d.property === 'padding' || d.property.startsWith('padding-')) &&
			!/^(0(px)?\s*)+$/.test(d.value)
	);
	const borderBox = declarations.some(
		(d) => d.property === 'box-sizing' && d.value === 'border-box'
	);
	return fillsHeight && padded && !borderBox;
}

function check(css: string): boolean {
	return rulesOf(css).some((rule) => overflowsParent(rule.declarations));
}

describe('All-Star boxes fit their frames', () => {
	it('finds the All-Star components to check', () => {
		expect(files.length).toBeGreaterThanOrEqual(15);
	});

	it('flags a rule that fills its parent with a padding and content-box sizing', () => {
		expect(check('.a { height: 100%; padding: var(--x); }')).toBe(true);
	});

	it('passes a rule with zero padding, no padding or border-box sizing', () => {
		expect(check('.a { height: 100%; padding: 0; }')).toBe(false);
		expect(check('.a { height: 100%; }')).toBe(false);
		expect(check('.a { box-sizing: border-box; height: 100%; padding: var(--x); }')).toBe(false);
		expect(check('.a { min-height: 100%; padding: var(--x); }')).toBe(false);
	});

	it('keeps every All-Star box that fills its parent inside it', () => {
		const offenders: string[] = [];
		for (const file of files) {
			const style = styleOf(readFileSync(join(componentsDir, file), 'utf8'));
			for (const rule of rulesOf(style)) {
				if (overflowsParent(rule.declarations)) offenders.push(`${file} ${rule.selector}`);
			}
		}
		expect(offenders, 'rules with height 100% and a padding but no box-sizing: border-box').toEqual(
			[]
		);
	});
});
