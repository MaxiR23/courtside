import { absoluteUrl } from '#lib/meta/head.ts';

/** The AI user agents robots.txt asks to stay out. See docs/adr/0085. */
export const AI_USER_AGENTS = [
	'GPTBot',
	'OAI-SearchBot',
	'ChatGPT-User',
	'ClaudeBot',
	'Claude-User',
	'Claude-SearchBot',
	'anthropic-ai',
	'CCBot',
	'Google-Extended',
	'Applebot-Extended',
	'PerplexityBot',
	'Perplexity-User',
	'Meta-ExternalAgent',
	'Bytespider',
	'Amazonbot',
	'cohere-ai'
] as const;

/** The robots.txt body: AI agents out, everyone else in except /preview, the sitemap with a site URL. */
export function robotsTxt(siteUrl: string | undefined): string {
	const lines = [
		'# Search engines are welcome. AI crawlers are asked to stay out (docs/adr/0085).',
		...AI_USER_AGENTS.map((agent) => `User-agent: ${agent}`),
		'Disallow: /',
		'',
		'User-agent: *',
		'Disallow: /preview'
	];
	if (siteUrl) lines.push('', `Sitemap: ${absoluteUrl(siteUrl, '/sitemap.xml')}`);
	return lines.join('\n') + '\n';
}

/** The sitemap.xml body: one url per path with a site URL, an empty urlset without one. */
export function sitemapXml(siteUrl: string | undefined, paths: readonly string[]): string {
	const urls = siteUrl
		? paths.map((path) => `<url><loc>${absoluteUrl(siteUrl, path)}</loc></url>`)
		: [];
	return [
		'<?xml version="1.0" encoding="UTF-8"?>',
		'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
		...urls,
		'</urlset>',
		''
	].join('\n');
}
