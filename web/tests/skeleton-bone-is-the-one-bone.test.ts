// web/tests/skeleton-bone-is-the-one-bone.test.ts
//
// Cross-cutting test: the loading skeleton bone lives in SkeletonBone, so no other component or
// route defines a .bone rule or leaves markup with a bone class.
//
// Tested:
// - The components and routes to scan are found, and the scan cannot pass by finding no file
// - The matcher flags a .bone rule, and passes other bone names and comments
// - SkeletonBone defines the bone
// - No other component or route defines a .bone rule
// - No other component or route has markup with a bone class
//
// What is covered:
// - Happy path (only SkeletonBone), edge cases (lookalike names, a selector list, a comment)
//   and the error case (a rule that defines a bone is flagged)
//
// Run with: cd web && pnpm exec vitest run tests/skeleton-bone-is-the-one-bone.test.ts
//
// SEE: web/src/lib/components/SkeletonBone.svelte
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const srcDir = join(import.meta.dirname, '../src');
const routesDir = join(srcDir, 'routes');
const componentsDir = join(srcDir, 'lib/components');
const owner = join(componentsDir, 'SkeletonBone.svelte');

type Rule = { selectors: string[] };

function styleOf(source: string): string {
	const match = source.match(/<style[^>]*>([\s\S]*?)<\/style>/);
	return (match?.[1] ?? '').replace(/\/\*[\s\S]*?\*\//g, '');
}

function markupOf(source: string): string {
	return source.replace(/<style[^>]*>[\s\S]*?<\/style>/g, '');
}

function rulesOf(style: string): Rule[] {
	const rules: Rule[] = [];
	for (const match of style.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
		const selectors = (match[1] ?? '').split(',').map((selector) => selector.trim());
		rules.push({ selectors });
	}
	return rules;
}

/** Whether any selector of any rule of the CSS targets the .bone class. */
function definesBone(css: string): boolean {
	return rulesOf(css).some((rule) => rule.selectors.some((s) => /\.bone(?![\w-])/.test(s)));
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
const others = [...componentFiles, ...routeFiles].filter((file) => file !== owner);

describe('the scan', () => {
	it('finds the components and routes to check', () => {
		expect(componentFiles.length).toBeGreaterThanOrEqual(100);
		expect(routeFiles.some((file) => file.endsWith('+page.svelte'))).toBe(true);
	});
});

describe('the matcher', () => {
	it('flags a .bone rule, and passes other bone names and comments', () => {
		expect(definesBone('.bone { x: y; }')).toBe(true);
		expect(definesBone('.card-bone .bone { x: y; }')).toBe(true);
		expect(definesBone('.a, .bone:hover { x: y; }')).toBe(true);
		expect(definesBone('.bones { x: y; }')).toBe(false);
		expect(definesBone('.card-bone { x: y; }')).toBe(false);
		expect(definesBone('.tag-bone { x: y; }')).toBe(false);
		expect(definesBone('.frame-bone-wrap { x: y; }')).toBe(false);
		expect(definesBone(styleOf('<style>/* .bone { } */ .a { x: y; }</style>'))).toBe(false);
	});
});

describe('the one bone', () => {
	it('defines the bone in SkeletonBone', () => {
		expect(definesBone(styleOf(readFileSync(owner, 'utf8')))).toBe(true);
	});

	it('is the only component or route that defines a .bone rule', () => {
		const offenders = others
			.filter((file) => definesBone(styleOf(readFileSync(file, 'utf8'))))
			.map((file) => relative(srcDir, file));
		expect(offenders, `define a .bone rule outside SkeletonBone: ${offenders.join(', ')}`).toEqual(
			[]
		);
	});

	it('leaves no other markup with a bone class', () => {
		const offenders = others
			.filter((file) =>
				/class="(?:[^"]*\s)?bone(?:\s[^"]*)?"/.test(markupOf(readFileSync(file, 'utf8')))
			)
			.map((file) => relative(srcDir, file));
		expect(offenders, `have markup with a bone class: ${offenders.join(', ')}`).toEqual([]);
	});
});
