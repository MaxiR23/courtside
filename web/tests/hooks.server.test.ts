// web/tests/hooks.server.test.ts
//
// Tests for the server hook that writes the page language and direction, and the head tags of
// the files the browser fills in.
//
// Tested:
// - Writes English and left-to-right when the request names no language
// - Writes Spanish when the request prefers Spanish
// - Leaves no paraglide placeholder in the page
// - A page with no <title> gets its title, description, Open Graph and Twitter tags and, with a
//   site URL, an absolute canonical; the fallback gets the home's wording and no canonical
// - The series page gets no canonical; with no site URL no page gets one
// - A page that already has a <title> is left as it is, apart from the language
// - A Spanish request gets Spanish tags
//
// What is covered:
// - Happy path and the default case, through the real paraglide middleware
// - Edge cases: fallback path, series path, no site URL, a page with its own title
//
// Run with: cd web && pnpm exec vitest run tests/hooks.server.test.ts
//
// SEE: web/src/hooks.server.ts
// @vitest-environment node
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { RequestEvent } from '@sveltejs/kit';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const config = vi.hoisted(() => ({ siteUrl: undefined as string | undefined }));
vi.mock('../src/lib/feed/config', () => ({
	get siteUrl() {
		return config.siteUrl;
	}
}));

import { handle } from '../src/hooks.server';

const htmlLine = readFileSync(join(import.meta.dirname, '../src/app.html'), 'utf8')
	.split('\n')
	.find((line) => line.startsWith('<html'))!;

const head = (inner: string) => `${htmlLine}\n<head>${inner}</head>`;

async function render(
	headers: Record<string, string> = {},
	{ path = '/', chunk = htmlLine }: { path?: string; chunk?: string } = {}
): Promise<string> {
	const url = new URL(`http://localhost${path}`);
	const request = new Request(url, { headers });
	let html = '';
	await handle({
		event: { request, url } as RequestEvent,
		resolve: async (_event, options) => {
			html = (await options?.transformPageChunk?.({ html: chunk, done: true })) ?? chunk;
			return new Response(html);
		}
	});
	return html;
}

beforeEach(() => {
	config.siteUrl = undefined;
});

describe('the server hook', () => {
	it('writes English and left-to-right when no language is requested', async () => {
		const html = await render();
		expect(html).toContain('lang="en"');
		expect(html).toContain('dir="ltr"');
	});

	it('writes Spanish when the request prefers Spanish', async () => {
		const html = await render({ 'accept-language': 'es' });
		expect(html).toContain('lang="es"');
	});

	it('leaves no paraglide placeholder in the page', async () => {
		expect(await render()).not.toContain('%paraglide.');
	});

	describe('head tags for a page with no title', () => {
		const shell = head('<meta charset="utf-8">');
		const has = (html: string, needle: string) => expect(html).toContain(needle);

		it('writes the title, description, Open Graph and Twitter tags and the canonical', async () => {
			config.siteUrl = 'https://www.example.com';
			const html = await render({}, { path: '/standings', chunk: shell });
			has(html, '<title>Standings · Courtside</title>');
			has(html, 'name="description" content="NBA standings for the East and the West');
			has(html, 'property="og:title" content="Standings · Courtside"');
			has(html, 'property="og:image" content="https://www.example.com/og-image.png"');
			has(html, 'name="twitter:card" content="summary_large_image"');
			has(html, '<link rel="canonical" href="https://www.example.com/standings" data-shell-meta>');
			has(html, 'property="og:url" content="https://www.example.com/standings"');
			expect(html.indexOf('<title>')).toBeLessThan(html.indexOf('</head>'));
		});

		it('gives the fallback the home wording and no canonical', async () => {
			config.siteUrl = 'https://www.example.com';
			const html = await render({}, { path: '/[fallback]', chunk: shell });
			has(html, '<title>Courtside</title>');
			has(html, 'Live NBA scores');
			expect(html).not.toContain('canonical');
			expect(html).not.toContain('og:url');
		});

		it('gives the series page no canonical', async () => {
			config.siteUrl = 'https://www.example.com';
			const html = await render({}, { path: '/playoffs/series', chunk: shell });
			has(html, '<title>Playoffs · Courtside</title>');
			expect(html).not.toContain('canonical');
		});

		it('writes no canonical anywhere without a site URL', async () => {
			for (const path of ['/', '/cup', '/all-star/previous', '/[fallback]']) {
				const html = await render({}, { path, chunk: shell });
				expect(html, path).not.toContain('canonical');
				expect(html, path).toContain('property="og:image" content="/og-image.png"');
			}
		});

		it('leaves a page that has a title as it is, apart from the language', async () => {
			config.siteUrl = 'https://www.example.com';
			const own = head('<title>Own</title>');
			const html = await render({}, { path: '/', chunk: own });
			expect(html).toBe(own.replace('%paraglide.lang%', 'en').replace('%paraglide.dir%', 'ltr'));
		});

		it('leaves a chunk with no head alone', async () => {
			const html = await render({}, { chunk: '<body></body>' });
			expect(html).toBe('<body></body>');
		});

		it('writes Spanish tags for a Spanish request', async () => {
			const html = await render({ 'accept-language': 'es' }, { path: '/standings', chunk: shell });
			has(html, '<title>Clasificación · Courtside</title>');
			has(html, 'property="og:locale" content="es_ES"');
			has(html, 'Clasificación de la NBA');
		});
	});
});
