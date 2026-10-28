// web/tests/no-time-at-build.test.ts
//
// Cross-cutting test: no time is formatted at build time, because the build has no viewer zone.
// Every page except the home renders in the browser only, and the home formats nothing itself.
//
// Tested:
// - The page files to scan are found, and the scan cannot pass by finding no file
// - Each non-root route page has a +page.ts that sets `export const ssr = false;`
// - The root page imports no time or locale formatter
// - The preview route is left out: it exists only in development
//
// What is covered:
// - Happy path (every page complies) and the error case (a source without ssr = false is flagged)
//
// Run with: cd web && pnpm exec vitest run tests/no-time-at-build.test.ts
//
// SEE: web/src/lib/format/time.ts, docs/adr/0082-tip-times-in-the-viewers-time-zone.md
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const routesDir = join(import.meta.dirname, '../src/routes');

function pagesUnder(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) return entry.name === 'preview' ? [] : pagesUnder(path);
		return entry.name === '+page.svelte' ? [path] : [];
	});
}

const turnsOffSsr = (source: string): boolean => /^export const ssr = false;$/m.test(source);

const rootPage = join(routesDir, '+page.svelte');
const innerPages = pagesUnder(routesDir).filter((file) => file !== rootPage);

describe('the ssr scan', () => {
	it('flags a source without ssr = false', () => {
		expect(turnsOffSsr('export const prerender = true;')).toBe(false);
		expect(turnsOffSsr('export const ssr = false;\n')).toBe(true);
	});

	it('finds the page files, so the scan cannot pass by finding none', () => {
		expect(innerPages.length).toBeGreaterThanOrEqual(10);
	});
});

describe('every page but the root', () => {
	for (const file of innerPages) {
		it(`${relative(routesDir, file)} sets ssr = false`, () => {
			const script = join(dirname(file), '+page.ts');
			expect(existsSync(script)).toBe(true);
			expect(turnsOffSsr(readFileSync(script, 'utf8'))).toBe(true);
		});
	}
});

describe('the root page', () => {
	it('imports no time or locale formatter', () => {
		const source = readFileSync(rootPage, 'utf8');
		expect(source).not.toMatch(/#lib\/format\/(time|locale)\.ts/);
	});
});
