// web/tests/every-page-has-the-footer.test.ts
//
// Cross-cutting test: the footer line (the unofficial-site disclaimer) shows on every page, so every
// page file, or the page component it renders, has the SiteFooter at the top level of its markup.
//
// Tested:
// - The page files to scan are found, and the scan cannot pass by finding no file
// - Each route page, or the page component it imports, renders <SiteFooter /> at column 0
// - The preview route is left out: it is a component catalog, not a page
//
// What is covered:
// - Happy path (every page has it) and the error case (a source without the footer is flagged)
//
// Run with: cd web && pnpm exec vitest run tests/every-page-has-the-footer.test.ts
//
// SEE: web/src/lib/components/SiteFooter.svelte, web/tests/lib/components/SiteFooter.test.ts
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const srcDir = join(import.meta.dirname, '../src');
const routesDir = join(srcDir, 'routes');
const componentsDir = join(srcDir, 'lib/components');

function pagesUnder(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) return entry.name === 'preview' ? [] : pagesUnder(path);
		return entry.name === '+page.svelte' ? [path] : [];
	});
}

/** The source that renders the page: the page component it imports, else the route file itself. */
function renderedSource(routeFile: string): string {
	const source = readFileSync(routeFile, 'utf8');
	const imported = source.match(/#lib\/components\/(\w+Page)\.svelte/);
	return imported ? readFileSync(join(componentsDir, `${imported[1]}.svelte`), 'utf8') : source;
}

const hasFooter = (source: string): boolean => /^<SiteFooter \/>$/m.test(source);

describe('the footer scan', () => {
	it('flags a source without the footer, and one that nests it', () => {
		expect(hasFooter('<main></main>')).toBe(false);
		expect(hasFooter('{#if a}\n\t<SiteFooter />\n{/if}')).toBe(false);
		expect(hasFooter('<main></main>\n<SiteFooter />\n')).toBe(true);
	});

	it('finds the page files, so the scan cannot pass by finding none', () => {
		expect(pagesUnder(routesDir).length).toBeGreaterThanOrEqual(10);
	});
});

describe('every page', () => {
	for (const file of pagesUnder(routesDir)) {
		it(`${relative(routesDir, file)} renders the footer`, () => {
			expect(hasFooter(renderedSource(file))).toBe(true);
		});
	}
});
