import { siteUrl } from '#lib/feed/config.ts';
import { sitemapXml } from '#lib/meta/crawl.ts';
import { sitemapPaths } from '#lib/meta/pages.ts';

export const prerender = true;

export function GET(): Response {
	return new Response(sitemapXml(siteUrl, sitemapPaths()), {
		headers: { 'content-type': 'application/xml; charset=utf-8' }
	});
}
