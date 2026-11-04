// web/tests/lib/meta/head.test.ts
//
// Tests for the head tag builder.
//
// Tested:
// - Builds the description, canonical, Open Graph and Twitter tags with a site URL
// - Leaves out canonical and og:url without a site URL or without a path
// - Writes the image root-relative without a site URL
// - Writes og:locale for English and Spanish, and the site name and image alt in the language
// - canonicalPath keeps only the listed query parameters
// - shellHead escapes & < > and ", and marks every tag but the title
//
// What is covered:
// - Happy path, edge cases (no site URL, no path) and the escaping error case of pure functions
//
// Run with: cd web && pnpm exec vitest run tests/lib/meta/head.test.ts
//
// SEE: web/src/lib/meta/head.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
	absoluteUrl,
	canonicalPath,
	headTags,
	ogLocale,
	shellHead,
	SHELL_MARK,
	type HeadTag
} from '../../../src/lib/meta/head';
import { preferLanguages } from '../../prefer-languages';

afterEach(() => {
	vi.restoreAllMocks();
});

const base = {
	title: 'Standings · Courtside',
	description: 'A description.',
	path: '/standings?season=2005',
	siteUrl: 'https://www.example.com' as string | undefined,
	locale: 'en'
};

function content(
	tags: HeadTag[],
	key: 'name' | 'property' | 'rel',
	value: string
): string | undefined {
	const found = tags.find((tag) => tag.attributes[key] === value);
	return found?.attributes.content ?? found?.attributes.href;
}

describe('headTags', () => {
	it('builds every tag with a site URL', () => {
		const tags = headTags(base);
		expect(content(tags, 'name', 'description')).toBe('A description.');
		expect(content(tags, 'rel', 'canonical')).toBe('https://www.example.com/standings?season=2005');
		expect(content(tags, 'property', 'og:type')).toBe('website');
		expect(content(tags, 'property', 'og:site_name')).toBe('Courtside');
		expect(content(tags, 'property', 'og:title')).toBe('Standings · Courtside');
		expect(content(tags, 'property', 'og:description')).toBe('A description.');
		expect(content(tags, 'property', 'og:url')).toBe(
			'https://www.example.com/standings?season=2005'
		);
		expect(content(tags, 'property', 'og:image')).toBe('https://www.example.com/og-image.png');
		expect(content(tags, 'property', 'og:image:width')).toBe('1200');
		expect(content(tags, 'property', 'og:image:height')).toBe('630');
		expect(content(tags, 'property', 'og:image:alt')).toBe('The Courtside logo and name');
		expect(content(tags, 'property', 'og:locale')).toBe('en_US');
		expect(content(tags, 'name', 'twitter:card')).toBe('summary_large_image');
	});

	it('leaves out canonical and og:url without a site URL, and keeps the image root-relative', () => {
		const tags = headTags({ ...base, siteUrl: undefined });
		expect(content(tags, 'rel', 'canonical')).toBeUndefined();
		expect(content(tags, 'property', 'og:url')).toBeUndefined();
		expect(content(tags, 'property', 'og:image')).toBe('/og-image.png');
		expect(content(tags, 'name', 'description')).toBe('A description.');
	});

	it('leaves out canonical and og:url without a path', () => {
		const tags = headTags({ ...base, path: null });
		expect(content(tags, 'rel', 'canonical')).toBeUndefined();
		expect(content(tags, 'property', 'og:url')).toBeUndefined();
		expect(content(tags, 'property', 'og:image')).toBe('https://www.example.com/og-image.png');
	});

	it('follows the active language for the site name, image alt and locale', () => {
		preferLanguages(['es']);
		const tags = headTags({ ...base, locale: 'es' });
		expect(content(tags, 'property', 'og:image:alt')).toBe('El logo y el nombre de Courtside');
		expect(content(tags, 'property', 'og:locale')).toBe('es_ES');
	});
});

describe('ogLocale, canonicalPath and absoluteUrl', () => {
	it('maps the two languages and passes an unknown one through', () => {
		expect(ogLocale('en')).toBe('en_US');
		expect(ogLocale('es')).toBe('es_ES');
		expect(ogLocale('fr')).toBe('fr');
	});

	it('keeps only the listed query parameters in the canonical path', () => {
		expect(
			canonicalPath(new URL('https://x.test/playoffs/series?id=east-r1-1&season=2005'), [
				'id',
				'season'
			])
		).toBe('/playoffs/series?id=east-r1-1&season=2005');
		expect(canonicalPath(new URL('https://x.test/cup'), ['season'])).toBe('/cup');
		expect(canonicalPath(new URL('https://x.test/standings?fbclid=abc'), ['season'])).toBe(
			'/standings'
		);
		expect(
			canonicalPath(new URL('https://x.test/standings?season=2005&fbclid=abc'), ['season'])
		).toBe('/standings?season=2005');
	});

	it('joins the origin and the path', () => {
		expect(absoluteUrl('https://www.example.com', '/cup')).toBe('https://www.example.com/cup');
	});
});

describe('shellHead', () => {
	it('writes the title and marks every other tag', () => {
		const html = shellHead({ title: 'Cup · Courtside', tags: headTags(base) });
		expect(html.startsWith('<title>Cup · Courtside</title>')).toBe(true);
		const lines = html.split('\n').map((line) => line.trim());
		expect(lines[0]).toBe('<title>Cup · Courtside</title>');
		for (const line of lines.slice(1)) expect(line.endsWith(`${SHELL_MARK}>`)).toBe(true);
		expect(html).toContain(
			'<link rel="canonical" href="https://www.example.com/standings?season=2005"'
		);
	});

	it('escapes & < > and " in values and the title', () => {
		const html = shellHead({
			title: 'A & <B>',
			tags: [{ tag: 'meta', attributes: { name: 'description', content: 'a & "b" <c>' } }]
		});
		expect(html).toContain('<title>A &amp; &lt;B&gt;</title>');
		expect(html).toContain('content="a &amp; &quot;b&quot; &lt;c&gt;"');
	});
});
