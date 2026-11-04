// web/tests/lib/meta/pages.test.ts
//
// Tests for the table of prerendered pages.
//
// Tested:
// - The table's keys equal the paths of every route page with no [param] segment, outside preview
// - sitemapPaths lists 6 paths, not /playoffs/series and not /preview
// - Every title is the one the route showed before, in English and Spanish
// - Every meta description message is under 160 characters in both languages
//
// What is covered:
// - Happy path and the length limit, on the table and on the folder it mirrors
//
// Run with: cd web && pnpm exec vitest run tests/lib/meta/pages.test.ts
//
// SEE: web/src/lib/meta/pages.ts
import { readdirSync } from 'node:fs';
import { join, sep } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { prerenderedPages, sitemapPaths } from '../../../src/lib/meta/pages';
import * as messages from '../../../src/lib/paraglide/messages.js';
import { preferLanguages } from '../../prefer-languages';

afterEach(() => {
	vi.restoreAllMocks();
});

const routesDir = join(import.meta.dirname, '../../../src/routes');

const routePaths = readdirSync(routesDir, { recursive: true, encoding: 'utf8' })
	.filter((file) => file.endsWith('+page.svelte'))
	.map((file) => file.split(sep).slice(0, -1))
	.filter((segments) => !segments.some((s) => s.startsWith('[')) && segments[0] !== 'preview')
	.map((segments) => '/' + segments.join('/'));

describe('prerenderedPages', () => {
	it('names every route page that has no parameter, outside preview', () => {
		expect(routePaths.length).toBeGreaterThan(5);
		expect(Object.keys(prerenderedPages).sort()).toEqual([...routePaths].sort());
	});

	it('lists 6 paths in the sitemap, not the series page and not /preview', () => {
		const paths = sitemapPaths();
		expect(paths).toHaveLength(6);
		expect(paths).not.toContain('/playoffs/series');
		expect(paths.some((path) => path.includes('preview'))).toBe(false);
	});

	it('titles each page as its route does', () => {
		const titles = Object.fromEntries(
			Object.entries(prerenderedPages).map(([path, page]) => [path, page.title()])
		);
		expect(titles).toEqual({
			'/': 'Courtside',
			'/standings': 'Standings · Courtside',
			'/cup': 'NBA Cup · Courtside',
			'/playoffs': 'Playoffs · Courtside',
			'/playoffs/series': 'Playoffs · Courtside',
			'/all-star': 'All-Star · Courtside',
			'/all-star/previous': 'All-Star · Courtside'
		});
	});

	it('titles each page in Spanish', () => {
		preferLanguages(['es']);
		expect(prerenderedPages['/standings'].title()).toBe('Clasificación · Courtside');
		expect(prerenderedPages['/cup'].title()).toBe('Copa NBA · Courtside');
	});

	it('describes each page, in English and Spanish', () => {
		const english = Object.values(prerenderedPages).map((page) => page.description());
		preferLanguages(['es']);
		const spanish = Object.values(prerenderedPages).map((page) => page.description());
		expect(new Set(english).size).toBe(english.length - 1);
		for (let i = 0; i < english.length; i++) expect(spanish[i]).not.toBe(english[i]);
	});
});

describe('the meta description messages', () => {
	const name = 'N'.repeat(40);
	const describers = Object.entries(messages).filter(([key]) =>
		key.startsWith('meta_description_')
	);

	it('finds the messages, so the check cannot pass on none', () => {
		expect(describers).toHaveLength(13);
	});

	it.each(['en', 'es'])('are under 160 characters in %s', (language) => {
		preferLanguages([language]);
		for (const [key, message] of describers) {
			const text = (message as (input: Record<string, string>) => string)({
				name,
				away: name,
				home: name
			});
			expect(text.length, key).toBeLessThan(160);
		}
	});
});
