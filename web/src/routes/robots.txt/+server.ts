import { siteUrl } from '#lib/feed/config.ts';
import { robotsTxt } from '#lib/meta/crawl.ts';

export const prerender = true;

export function GET(): Response {
	return new Response(robotsTxt(siteUrl), {
		headers: { 'content-type': 'text/plain; charset=utf-8' }
	});
}
