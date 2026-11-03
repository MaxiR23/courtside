// web/tests/news-links-stay-in-the-site.test.ts
//
// Cross-cutting test: no news element has a link that leaves the site. Every href in the news
// components and the two news routes is an expression built from a prop or from resolve, never a
// literal URL, and no link opens a new tab or is marked external.
//
// Tested:
// - The files to scan are found, and the scan cannot pass by finding no file
// - The matcher flags an href with a literal scheme, a protocol-relative expression, target and rel="external"
// - No news component or news route has such a link
//
// What is covered:
// - Happy path (the news files comply) and the error case (each form is flagged)
//
// Run with: cd web && pnpm exec vitest run tests/news-links-stay-in-the-site.test.ts
//
// SEE: web/src/lib/components/NewsCard.svelte, docs/design-news.md
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const srcDir = join(import.meta.dirname, '../src');
const componentsDir = join(srcDir, 'lib', 'components');
const newsRoutes = [
	join(srcDir, 'routes', 'news', '+page.svelte'),
	join(srcDir, 'routes', 'news', '[id]', '+page.svelte')
];

const files = [
	...readdirSync(componentsDir)
		.filter((name) => /^(News.*|HomeNews)\.svelte$/.test(name))
		.map((name) => join(componentsDir, name)),
	...newsRoutes
];

/** The reasons a source holds a link that could leave the site. */
function leavingLinks(source: string): string[] {
	const found: string[] = [];
	for (const match of source.matchAll(/\bhref\s*=\s*("[^"]*"|'[^']*'|\{[^}]*\})/g)) {
		const value = match[1] ?? '';
		if (
			/:\/\/|^["']?\/\//.test(value) ||
			/\{\s*['"`]\s*\/\//.test(value) ||
			/['"`]\w+:\/\//.test(value)
		) {
			found.push(`href ${value}`);
		} else if (/^["']/.test(value)) {
			found.push(`literal href ${value}`);
		}
	}
	if (/\btarget\s*=/.test(source)) found.push('target');
	if (/\brel\s*=\s*["'][^"']*external/.test(source)) found.push('rel external');
	return found;
}

describe('the news link scan', () => {
	it('flags a literal URL, a protocol-relative expression, target and rel external', () => {
		expect(leavingLinks('<a href="https://x.example">x</a>')).not.toEqual([]);
		expect(leavingLinks("<a href={'//x.example'}>x</a>")).not.toEqual([]);
		expect(leavingLinks('<a href={link} target="_blank">x</a>')).toContain('target');
		expect(leavingLinks('<a href={link} rel="external">x</a>')).toContain('rel external');
	});

	it('passes an href built from a prop or resolve', () => {
		expect(leavingLinks('<a href={noteHref(card.id)}>x</a>')).toEqual([]);
		expect(leavingLinks('<a {href}>x</a>')).toEqual([]);
	});

	it('finds the news files, so the scan cannot pass by finding none', () => {
		expect(files.length).toBeGreaterThanOrEqual(10);
	});
});

describe('the news components and routes', () => {
	for (const file of files) {
		it(`${relative(srcDir, file)} holds no link that leaves the site`, () => {
			expect(leavingLinks(readFileSync(file, 'utf8'))).toEqual([]);
		});
	}
});
