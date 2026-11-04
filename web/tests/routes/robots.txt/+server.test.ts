// web/tests/routes/robots.txt/+server.test.ts
//
// Tests for the robots.txt route.
//
// Tested:
// - The route is prerendered
// - GET answers 200 as plain text with the body robotsTxt builds, with and without a site URL
//
// What is covered:
// - Happy path and the no-site-URL edge case; the config module is mocked
//
// Run with: cd web && pnpm exec vitest run tests/routes/robots.txt/+server.test.ts
//
// SEE: web/src/routes/robots.txt/+server.ts
import { beforeEach, describe, expect, it, vi } from 'vitest';

const config = vi.hoisted(() => ({ siteUrl: undefined as string | undefined }));
vi.mock('../../../src/lib/feed/config', () => ({
	get siteUrl() {
		return config.siteUrl;
	}
}));

import { robotsTxt } from '../../../src/lib/meta/crawl';
import { GET, prerender } from '../../../src/routes/robots.txt/+server';

beforeEach(() => {
	config.siteUrl = undefined;
});

describe('the robots.txt route', () => {
	it('is prerendered', () => {
		expect(prerender).toBe(true);
	});

	it('answers the body for the site URL, as plain text', async () => {
		config.siteUrl = 'https://www.example.com';
		const response = GET();
		expect(response.status).toBe(200);
		expect(response.headers.get('content-type')).toBe('text/plain; charset=utf-8');
		const body = await response.text();
		expect(body).toBe(robotsTxt('https://www.example.com'));
		expect(body).toContain('Sitemap: https://www.example.com/sitemap.xml');
	});

	it('answers a body with no URL when there is no site URL', async () => {
		const body = await GET().text();
		expect(body).toBe(robotsTxt(undefined));
		expect(body).not.toContain('http');
	});
});
