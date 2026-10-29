// web/tests/tag-is-the-one-tag.test.ts
//
// Cross-cutting test: the tag (a hairline box around a short label) lives in Tag, so no other
// component or route writes the tag box or the solid tag fill on its own rule.
//
// Tested:
// - The components and routes to scan are found, and the scan cannot pass by finding no file
// - The matcher flags a rule that reads the tag padding, and a solid accent fill with an accent
//   border or the tag padding, and passes an accent fill alone, a divider border and comments
// - Tag holds a tag border rule and a solid tag rule
// - Every listed exception still holds its rule, so the list never keeps a stale entry
// - No other component or route holds a tag border rule or a solid tag rule, except the non-tags
//
// What is covered:
// - Happy path (only Tag and the listed non-tags hold them), edge cases (a selector list, a
//   media query, a two-value padding, a comment) and the error case (a stray rule is flagged)
// - The definition of a tag is the --tag-padding token (or, in a padding declaration, the
//   --cup-year-tag-padding or --bracket-tick-size token), or a solid accent fill with an accent
//   border. A tag written with another padding and no fill would pass; docs/design.md is the
//   rule of record
//
// Run with: cd web && pnpm exec vitest run tests/tag-is-the-one-tag.test.ts
//
// SEE: web/src/lib/components/Tag.svelte
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

function reads(rule: Rule, property: string, value: string): boolean {
	return rule.declarations.some((d) => d.property === property && d.value === value);
}

const sitePaddingTokens = ['var(--cup-year-tag-padding)', 'var(--bracket-tick-size)'];

function readsTagPadding(rule: Rule): boolean {
	return rule.declarations.some(
		(d) =>
			d.value.includes('var(--tag-padding)') ||
			(d.property === 'padding' && sitePaddingTokens.some((token) => d.value.includes(token)))
	);
}

function isTagBorderRule(rule: Rule): boolean {
	return readsTagPadding(rule);
}

function isSolidTagRule(rule: Rule): boolean {
	return (
		reads(rule, 'background', 'var(--color-accent)') &&
		reads(rule, 'color', 'var(--color-bg)') &&
		(reads(rule, 'border-color', 'var(--color-accent)') || readsTagPadding(rule))
	);
}

/** The selectors (joined with ', ') of every rule the matcher flags. */
function tagRules(css: string): string[] {
	return rulesOf(css)
		.filter((rule) => isTagBorderRule(rule) || isSolidTagRule(rule))
		.map((rule) => rule.selectors.join(', '));
}

function borderRules(css: string): string[] {
	return rulesOf(css)
		.filter(isTagBorderRule)
		.map((rule) => rule.selectors.join(', '));
}

function solidRules(css: string): string[] {
	return rulesOf(css)
		.filter(isSolidTagRule)
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
const tagFile = join(componentsDir, 'Tag.svelte');

// These rules match the definition of a tag and are not tags. File name (in lib/components) to
// selectors.
const exceptions: Record<string, string[]> = {
	'SearchOverlay.svelte': ['.esc'], // the overlay's close button
	'AllStarHeader.svelte': ['.button.primary'], // a button
	'AllStarTeams.svelte': ['.mark.win'], // a won-game square
	'LastGames.svelte': ['.square.win'] // a won-game square
};

describe('the scan', () => {
	it('finds the components and routes to check', () => {
		expect(componentFiles.length).toBeGreaterThanOrEqual(100);
		expect(routeFiles.some((file) => file.endsWith('+page.svelte'))).toBe(true);
	});
});

describe('the matcher', () => {
	it('flags a rule that reads the tag padding', () => {
		expect(tagRules('.a { padding: var(--tag-padding); }')).toEqual(['.a']);
		expect(tagRules('.a, .b { padding: var(--tag-padding); }')).toEqual(['.a, .b']);
		expect(tagRules('@media (min-width: 40rem) { .a { padding: var(--tag-padding); } }')).toEqual([
			'.a'
		]);
		expect(tagRules('.a { padding: var(--hairline) var(--tag-padding); }')).toEqual(['.a']);
	});

	it('flags the old cup year tag and bracket tag rules', () => {
		expect(
			tagRules(`.year-tag {
				font-size: var(--body-size);
				padding: var(--cup-year-tag-padding);
				border: var(--hairline) solid var(--color-accent);
				color: var(--color-accent-light);
			}`)
		).toEqual(['.year-tag']);
		expect(
			tagRules(`.tag {
				padding: var(--hairline) var(--bracket-tick-size);
				border: var(--hairline) solid var(--color-divider);
				font-size: var(--bracket-meta-size);
			}`)
		).toEqual(['.tag']);
	});

	it('flags a solid accent fill with an accent border or the tag padding', () => {
		const fill = 'background: var(--color-accent); color: var(--color-bg);';
		expect(tagRules(`.a { ${fill} border-color: var(--color-accent); }`)).toEqual(['.a']);
		expect(tagRules(`.a { ${fill} padding: var(--tag-padding); }`)).toEqual(['.a']);
	});

	it('passes an accent fill alone, a divider border and a comment', () => {
		expect(
			tagRules('.a { background: var(--color-accent); color: var(--color-bg); width: 1rem; }')
		).toEqual([]);
		expect(tagRules('.a { border: var(--hairline) solid var(--color-divider); }')).toEqual([]);
		expect(
			tagRules(styleOf('<style>/* padding: var(--tag-padding); */ .a { x: y; }</style>'))
		).toEqual([]);
	});
});

describe('the tag', () => {
	it('holds a tag border rule and a solid tag rule in Tag', () => {
		const css = styleOf(readFileSync(tagFile, 'utf8'));
		expect(borderRules(css)).toEqual(['.tag']);
		expect(solidRules(css)).toEqual(['.solid']);
	});

	it('every listed exception still holds its rule', () => {
		const stale: string[] = [];
		for (const [name, selectors] of Object.entries(exceptions)) {
			const found = tagRules(styleOf(readFileSync(join(componentsDir, name), 'utf8')));
			for (const selector of selectors) {
				if (!found.includes(selector)) stale.push(`${name} ${selector}`);
			}
		}
		expect(stale, `no longer hold the rule, drop from the list: ${stale.join(', ')}`).toEqual([]);
	});

	it('is the only place besides the listed non-tags that holds a tag border or solid tag rule', () => {
		const offenders: string[] = [];
		for (const file of [...componentFiles, ...routeFiles]) {
			if (file === tagFile) continue;
			const allowed = file.startsWith(componentsDir)
				? (exceptions[relative(componentsDir, file)] ?? [])
				: [];
			for (const selector of tagRules(styleOf(readFileSync(file, 'utf8')))) {
				if (!allowed.includes(selector)) offenders.push(`${relative(srcDir, file)} ${selector}`);
			}
		}
		expect(offenders, `hold a tag rule outside Tag:\n${offenders.join('\n')}`).toEqual([]);
	});
});
