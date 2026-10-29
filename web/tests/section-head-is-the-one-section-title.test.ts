// web/tests/section-head-is-the-one-section-title.test.ts
//
// Cross-cutting test: the section title (the h2 of a section, in Barlow Condensed, uppercase) lives
// in SectionHead, so no other component or route styles an h2 or reads a section title size.
//
// Tested:
// - The components and routes to scan are found, and the scan cannot pass by finding no file
// - The matcher flags an h2 type selector and a font size on a section title token, and passes
//   a class that only contains "h2", a line-height alone and comments
// - SectionHead holds the section title rules
// - No other component or route holds one
//
// What is covered:
// - Happy path (only SectionHead holds it), edge cases (a selector list, a descendant, a media
//   query, a line-height alone, a comment) and the error case (a rule that holds it is flagged)
//
// Run with: cd web && pnpm exec vitest run tests/section-head-is-the-one-section-title.test.ts
//
// SEE: web/src/lib/components/SectionHead.svelte
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

function svelteFilesUnder(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) return svelteFilesUnder(path);
		return entry.name.endsWith('.svelte') ? [path] : [];
	});
}

const H2_SELECTOR = /(^|[\s>+~(])h2(?![\w-])/;
const TITLE_TOKENS = ['var(--section-h2-size)', 'var(--detail-section-h2-size)'];

/** The selectors (joined with ', ') of every rule that styles an h2 or reads a section title size. */
function sectionTitleRules(css: string): string[] {
	return rulesOf(css)
		.filter(
			(rule) =>
				rule.selectors.some((selector) => H2_SELECTOR.test(selector)) ||
				rule.declarations.some(
					(d) => d.property === 'font-size' && TITLE_TOKENS.some((token) => d.value.includes(token))
				)
		)
		.map((rule) => rule.selectors.join(', '));
}

const componentFiles = svelteFilesUnder(componentsDir);
const routeFiles = svelteFilesUnder(routesDir);
const sectionHeadFile = join(componentsDir, 'SectionHead.svelte');

describe('the scan', () => {
	it('finds the components and routes to check', () => {
		expect(componentFiles.length).toBeGreaterThanOrEqual(100);
		expect(routeFiles.some((file) => file.endsWith('+page.svelte'))).toBe(true);
	});
});

describe('the matcher', () => {
	it('flags an h2 type selector', () => {
		expect(sectionTitleRules('h2 { margin: 0; }')).toEqual(['h2']);
		expect(sectionTitleRules('.a h2 { margin: 0; }')).toEqual(['.a h2']);
		expect(sectionTitleRules('header > h2 { margin: 0; }')).toEqual(['header > h2']);
		expect(sectionTitleRules('.a, h2 { margin: 0; }')).toEqual(['.a, h2']);
		expect(sectionTitleRules('h2.mvp { margin: 0; }')).toEqual(['h2.mvp']);
		expect(sectionTitleRules('@media (min-width: 40rem) { h2 { margin: 0; } }')).toEqual(['h2']);
	});

	it('flags a font size on a section title token', () => {
		expect(sectionTitleRules('.a { font-size: var(--section-h2-size); }')).toEqual(['.a']);
		expect(sectionTitleRules('.a { font-size: var(--detail-section-h2-size); }')).toEqual(['.a']);
	});

	it('passes a class that contains h2, a line-height alone and a comment', () => {
		expect(sectionTitleRules('.h2-like { margin: 0; }')).toEqual([]);
		expect(sectionTitleRules('.th2 { margin: 0; }')).toEqual([]);
		expect(sectionTitleRules('.a { line-height: var(--section-h2-line-height); }')).toEqual([]);
		expect(
			sectionTitleRules(styleOf('<style>/* h2 { margin: 0; } */ .a { x: y; }</style>'))
		).toEqual([]);
	});
});

describe('the section title', () => {
	it('is styled in SectionHead', () => {
		expect(
			sectionTitleRules(styleOf(readFileSync(sectionHeadFile, 'utf8'))).length
		).toBeGreaterThanOrEqual(1);
	});

	it('is styled by no other component or route', () => {
		const offenders: string[] = [];
		for (const file of [...componentFiles, ...routeFiles]) {
			if (file === sectionHeadFile) continue;
			for (const selector of sectionTitleRules(styleOf(readFileSync(file, 'utf8')))) {
				offenders.push(`${relative(srcDir, file)} ${selector}`);
			}
		}
		expect(
			offenders,
			`style a section title outside SectionHead:\n${offenders.join('\n')}`
		).toEqual([]);
	});
});
