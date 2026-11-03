// web/tests/news-card-is-the-one-note.test.ts
//
// Cross-cutting test: a note is drawn by NewsCard alone. Only NewsCard and NewsArticlePage use
// NewsPhoto and NewsTags, and no other component or route that handles a note card draws an image
// or its headline on its own.
//
// Tested:
// - The files to scan are found, and the scan cannot pass by finding none
// - The matcher flags an import of NewsPhoto or NewsTags, an img and a headline outside a NewsCard
// - Only NewsCard and NewsArticlePage import NewsPhoto and NewsTags
// - Every other file that handles a NewsCardView draws no img and no headline of its own
//
// What is covered:
// - Happy path (only the allowed files draw a note) and the error case on synthetic sources
//
// Run with: cd web && pnpm exec vitest run tests/news-card-is-the-one-note.test.ts
//
// SEE: web/src/lib/components/NewsCard.svelte, docs/design-news.md
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const srcDir = join(import.meta.dirname, '../src');
const ALLOWED = new Set(['NewsCard.svelte', 'NewsArticlePage.svelte']);

function svelteFiles(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) return entry.name === 'preview' ? [] : svelteFiles(path);
		return entry.name.endsWith('.svelte') ? [path] : [];
	});
}

const files = [
	...svelteFiles(join(srcDir, 'lib', 'components')),
	...svelteFiles(join(srcDir, 'routes'))
];

const importsPart = (source: string) => /import\s+News(Photo|Tags)\s+from/.test(source);
const markup = (source: string) =>
	source.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<style[\s\S]*?<\/style>/g, '');
const drawsImage = (source: string) => /<img\b/.test(markup(source));
const readsHeadline = (source: string) => /\.headline\b/.test(markup(source));

describe('the note scan', () => {
	it('flags an import of the parts, an img and a headline outside NewsCard', () => {
		expect(importsPart("import NewsPhoto from '#lib/components/NewsPhoto.svelte';")).toBe(true);
		expect(importsPart("import NewsTags from '#lib/components/NewsTags.svelte';")).toBe(true);
		expect(importsPart("import NewsCard from '#lib/components/NewsCard.svelte';")).toBe(false);
		expect(drawsImage('<script></script><img src={card.photo.url} alt="" />')).toBe(true);
		expect(readsHeadline('<h3>{card.headline}</h3>')).toBe(true);
		expect(readsHeadline('<NewsCard {card} />')).toBe(false);
	});

	it('finds the files, so the scan cannot pass by finding none', () => {
		expect(files.length).toBeGreaterThan(50);
		expect(files.some((file) => file.endsWith('NewsCard.svelte'))).toBe(true);
	});
});

describe('only NewsCard draws a note', () => {
	it('lets only NewsCard and NewsArticlePage import NewsPhoto and NewsTags', () => {
		const importers = files
			.filter((file) => importsPart(readFileSync(file, 'utf8')))
			.map((file) => relative(srcDir, file).split('/').at(-1));
		expect(importers.sort()).toEqual([...ALLOWED].sort());
	});

	it('draws no img and no headline of its own in any other file that handles a NewsCardView', () => {
		const handlers = files.filter((file) => {
			const source = readFileSync(file, 'utf8');
			return /\bNewsCardView\b/.test(source) && !ALLOWED.has(file.split('/').at(-1) ?? '');
		});
		expect(handlers.length).toBeGreaterThan(0);
		for (const file of handlers) {
			const source = readFileSync(file, 'utf8');
			expect(drawsImage(source), relative(srcDir, file)).toBe(false);
			expect(readsHeadline(source), relative(srcDir, file)).toBe(false);
		}
	});
});
