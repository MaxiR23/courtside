// web/tests/lib/components/PageMeta.test.ts
//
// Tests for the PageMeta component.
//
// Tested:
// - Draws the title, the description and the Open Graph and Twitter tags
// - With a site URL, canonical and og:url are the site and the path; without one, or with no path, neither
// - In Spanish, og:locale and the image alt follow the language
// - The noindex variant draws only the robots tag and no title
// - On mount it removes the tags the server hook wrote, and keeps the title
// - Updates the description when the prop changes
//
// What is covered:
// - Every state and option; there is no interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PageMeta.test.ts
//
// SEE: web/src/lib/components/PageMeta.svelte
import { cleanup, render } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const config = vi.hoisted(() => ({ siteUrl: undefined as string | undefined }));
vi.mock('../../../src/lib/feed/config', () => ({
	get siteUrl() {
		return config.siteUrl;
	}
}));

import PageMeta from '../../../src/lib/components/PageMeta.svelte';
import { preferLanguages } from '../../prefer-languages';

const meta = (selector: string) => document.head.querySelector(selector);
const value = (selector: string) =>
	meta(selector)?.getAttribute('content') ?? meta(selector)?.getAttribute('href');

beforeEach(() => {
	config.siteUrl = 'https://www.example.com';
	document.head.innerHTML = '';
});

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

const props = { title: 'Cup · Courtside', description: 'About the Cup.', path: '/cup' };

describe('PageMeta', () => {
	it('draws the title, description and all Open Graph and Twitter tags', () => {
		render(PageMeta, props);
		expect(document.title).toBe('Cup · Courtside');
		expect(value('meta[name="description"]')).toBe('About the Cup.');
		expect(value('meta[property="og:type"]')).toBe('website');
		expect(value('meta[property="og:site_name"]')).toBe('Courtside');
		expect(value('meta[property="og:title"]')).toBe('Cup · Courtside');
		expect(value('meta[property="og:description"]')).toBe('About the Cup.');
		expect(value('meta[property="og:image"]')).toBe('https://www.example.com/og-image.png');
		expect(value('meta[property="og:image:width"]')).toBe('1200');
		expect(value('meta[property="og:image:height"]')).toBe('630');
		expect(value('meta[property="og:image:alt"]')).toBe('The Courtside logo and name');
		expect(value('meta[property="og:locale"]')).toBe('en_US');
		expect(value('meta[name="twitter:card"]')).toBe('summary_large_image');
	});

	it('sets canonical and og:url from the site URL and the path', () => {
		render(PageMeta, props);
		expect(value('link[rel="canonical"]')).toBe('https://www.example.com/cup');
		expect(value('meta[property="og:url"]')).toBe('https://www.example.com/cup');
	});

	it('sets neither without a site URL', () => {
		config.siteUrl = undefined;
		render(PageMeta, props);
		expect(meta('link[rel="canonical"]')).toBeNull();
		expect(meta('meta[property="og:url"]')).toBeNull();
		expect(value('meta[property="og:image"]')).toBe('/og-image.png');
	});

	it('sets neither with no path', () => {
		render(PageMeta, { ...props, path: null });
		expect(meta('link[rel="canonical"]')).toBeNull();
		expect(meta('meta[property="og:url"]')).toBeNull();
	});

	it('follows the language for og:locale and the image alt', () => {
		preferLanguages(['es']);
		render(PageMeta, props);
		expect(value('meta[property="og:locale"]')).toBe('es_ES');
		expect(value('meta[property="og:image:alt"]')).toBe('El logo y el nombre de Courtside');
	});

	it('draws only the robots tag, and no title, when noindex', () => {
		render(PageMeta, { noindex: true });
		expect(value('meta[name="robots"]')).toBe('noindex');
		expect(document.head.querySelectorAll('meta')).toHaveLength(1);
		expect(meta('title')).toBeNull();
	});

	it('removes the tags the server hook wrote and keeps the title', async () => {
		document.head.innerHTML =
			'<title>Shell</title><meta name="description" content="Generic." data-shell-meta>' +
			'<link rel="canonical" href="https://www.example.com/" data-shell-meta>';
		render(PageMeta, props);
		await vi.waitFor(() =>
			expect(document.head.querySelectorAll('[data-shell-meta]')).toHaveLength(0)
		);
		expect(document.head.querySelectorAll('meta[name="description"]')).toHaveLength(1);
		expect(value('meta[name="description"]')).toBe('About the Cup.');
		expect(document.head.querySelectorAll('title')).toHaveLength(1);
		expect(document.title).toBe('Cup · Courtside');
	});

	it('updates the description when the prop changes', async () => {
		const { rerender } = render(PageMeta, props);
		await rerender({ ...props, description: 'Changed.' });
		expect(value('meta[name="description"]')).toBe('Changed.');
		expect(value('meta[property="og:description"]')).toBe('Changed.');
	});
});
