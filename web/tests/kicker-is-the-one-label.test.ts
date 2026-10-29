// web/tests/kicker-is-the-one-label.test.ts
//
// Cross-cutting test: the small uppercase label (11px, wide letter spacing) lives in Kicker, so no
// other component or route writes the whole label declaration set on its own rule.
//
// Tested:
// - The components and routes to scan are found, and the scan cannot pass by finding no file
// - The matcher flags a rule with the whole label set, and passes partial sets and comments
// - Kicker holds the label set
// - No other component or route holds the label set
//
// What is covered:
// - Happy path (only Kicker holds it), edge cases (a selector list, a
//   media query, a split set, a comment) and the error case (a rule that holds it is flagged)
//
// Run with: cd web && pnpm exec vitest run tests/kicker-is-the-one-label.test.ts
//
// SEE: web/src/lib/components/Kicker.svelte
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

const LABEL_SET: Declaration[] = [
	{ property: 'font-size', value: 'var(--label-size)' },
	{ property: 'letter-spacing', value: 'var(--label-letter-spacing)' },
	{ property: 'text-transform', value: 'uppercase' }
];

/** The selectors (joined with ', ') of every rule that holds the whole label set. */
function labelRules(css: string): string[] {
	return rulesOf(css)
		.filter((rule) =>
			LABEL_SET.every((want) =>
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
const kickerFile = join(componentsDir, 'Kicker.svelte');

describe('the scan', () => {
	it('finds the components and routes to check', () => {
		expect(componentFiles.length).toBeGreaterThanOrEqual(100);
		expect(routeFiles.some((file) => file.endsWith('+page.svelte'))).toBe(true);
	});
});

describe('the matcher', () => {
	const set =
		'font-size: var(--label-size); letter-spacing: var(--label-letter-spacing); text-transform: uppercase;';

	it('flags a rule with the whole label set', () => {
		expect(labelRules(`.a { ${set} }`)).toEqual(['.a']);
		expect(labelRules(`.a { ${set} color: var(--color-muted); }`)).toEqual(['.a']);
		expect(labelRules(`.a, .b { ${set} }`)).toEqual(['.a, .b']);
		expect(labelRules(`@media (min-width: 40rem) { .a { ${set} } }`)).toEqual(['.a']);
	});

	it('passes a partial set, a split set and a comment', () => {
		expect(
			labelRules(
				'.a { font-size: var(--label-size); letter-spacing: var(--label-letter-spacing); }'
			)
		).toEqual([]);
		expect(
			labelRules(
				`.a { font-size: var(--label-size); letter-spacing: var(--label-letter-spacing); } .a { text-transform: uppercase; }`
			)
		).toEqual([]);
		expect(labelRules(styleOf(`<style>/* ${set} */ .a { x: y; }</style>`))).toEqual([]);
	});
});

describe('the kicker', () => {
	it('holds the label set in Kicker', () => {
		expect(labelRules(styleOf(readFileSync(kickerFile, 'utf8')))).toEqual(['.kicker']);
	});

	it('is the only component or route that holds the label set', () => {
		const offenders: string[] = [];
		for (const file of [...componentFiles, ...routeFiles]) {
			if (file === kickerFile) continue;
			for (const selector of labelRules(styleOf(readFileSync(file, 'utf8')))) {
				offenders.push(`${relative(srcDir, file)} ${selector}`);
			}
		}
		expect(offenders, `hold the label set outside Kicker:\n${offenders.join('\n')}`).toEqual([]);
	});
});
