// web/tests/routes/sitemap.xml/+server.test.ts
//
// Tests for the sitemap.xml route.
//
// Tested:
// - The route is prerendered
// - GET answers 200 as XML with the body sitemapXml builds for the sitemap pages, with and
//   without a site URL
//
// What is covered:
// - Happy path and the no-site-URL edge case; the config module is mocked
//
// Run with: cd web && pnpm exec vitest run tests/routes/sitemap.xml/+server.test.ts
//
// SEE: web/src/routes/sitemap.xml/+server.ts
import { beforeEach, describe, expect, it, vi } from 'vitest';

const config = vi.hoisted(() => ({ siteUrl: undefined as string | undefined }));
vi.mock('../../../src/lib/feed/config', () => ({
	get siteUrl() {
		return config.siteUrl;
	}
}));

import { sitemapXml } from '../../../src/lib/meta/crawl';
import { sitemapPaths } from '../../../src/lib/meta/pages';
import { GET, prerender } from '../../../src/routes/sitemap.xml/+server';

beforeEach(() => {
	config.siteUrl = undefined;
});

describe('the sitemap.xml route', () => {
	it('is prerendered', () => {
		expect(prerender).toBe(true);
	});

	it('answers the body for the site URL, as XML', async () => {
		config.siteUrl = 'https://www.example.com';
		const response = GET();
		expect(response.status).toBe(200);
		expect(response.headers.get('content-type')).toBe('application/xml; charset=utf-8');
		const body = await response.text();
		expect(body).toBe(sitemapXml('https://www.example.com', sitemapPaths()));
		expect(body.match(/<loc>/g)).toHaveLength(6);
	});

	it('answers a body with no <loc> when there is no site URL', async () => {
		const body = await GET().text();
		expect(body).toBe(sitemapXml(undefined, sitemapPaths()));
		expect(body).not.toContain('<loc>');
	});
});
