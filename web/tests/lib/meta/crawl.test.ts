// web/tests/lib/meta/crawl.test.ts
//
// Tests for the robots.txt and sitemap.xml bodies.
//
// Tested:
// - AI_USER_AGENTS holds exactly the 16 names, and every one is in the Disallow: / group
// - The * group disallows only /preview; no group names Googlebot or Bingbot
// - With a site URL the last line is the Sitemap line; without one there is none and no http
// - sitemapXml lists one <loc> per path with a site URL, none without, and is well-formed
//
// What is covered:
// - Happy path, the no-site-URL edge case, and the well-formedness check of pure functions
//
// Run with: cd web && pnpm exec vitest run tests/lib/meta/crawl.test.ts
//
// SEE: web/src/lib/meta/crawl.ts
import { describe, expect, it } from 'vitest';

import { AI_USER_AGENTS, robotsTxt, sitemapXml } from '../../../src/lib/meta/crawl';

const site = 'https://www.example.com';

type Group = { agents: string[]; rules: string[] };

function groups(text: string): Group[] {
	const result: Group[] = [];
	let current: Group | null = null;
	for (const line of text.split('\n')) {
		if (line.startsWith('#') || line.startsWith('Sitemap:')) continue;
		if (!line.trim()) {
			current = null;
			continue;
		}
		if (line.startsWith('User-agent: ')) {
			if (!current) {
				current = { agents: [], rules: [] };
				result.push(current);
			}
			current.agents.push(line.slice('User-agent: '.length));
		} else current?.rules.push(line);
	}
	return result;
}

describe('AI_USER_AGENTS', () => {
	it('holds exactly the 16 names', () => {
		expect([...AI_USER_AGENTS]).toEqual([
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
		]);
	});
});

describe('robotsTxt', () => {
	it('disallows / for every AI agent in one group', () => {
		const ai = groups(robotsTxt(site)).filter((g) => g.rules.includes('Disallow: /'));
		expect(ai).toHaveLength(1);
		expect(ai[0].agents).toEqual([...AI_USER_AGENTS]);
		expect(ai[0].rules).toEqual(['Disallow: /']);
	});

	it('lets everyone else in except /preview, and names neither Googlebot nor Bingbot', () => {
		const all = groups(robotsTxt(site));
		expect(all).toHaveLength(2);
		expect(all[1]).toEqual({ agents: ['*'], rules: ['Disallow: /preview'] });
		expect(robotsTxt(site)).not.toMatch(/googlebot|bingbot/i);
		expect(robotsTxt(site).match(/^Disallow: \/$/gm)).toHaveLength(1);
	});

	it('ends with the sitemap line when there is a site URL', () => {
		const lines = robotsTxt(site).split('\n');
		expect(lines.at(-1)).toBe('');
		expect(lines.at(-2)).toBe(`Sitemap: ${site}/sitemap.xml`);
	});

	it('has no Sitemap line and no URL without a site URL', () => {
		const text = robotsTxt(undefined);
		expect(text).not.toContain('Sitemap');
		expect(text).not.toContain('http');
		expect(text.endsWith('Disallow: /preview\n')).toBe(true);
	});
});

describe('sitemapXml', () => {
	const paths = ['/', '/standings', '/cup'];

	it('lists one <loc> per path with the site URL', () => {
		const xml = sitemapXml(site, paths);
		expect([...xml.matchAll(/<loc>([^<]*)<\/loc>/g)].map((match) => match[1])).toEqual([
			`${site}/`,
			`${site}/standings`,
			`${site}/cup`
		]);
	});

	it('lists nothing without a site URL', () => {
		expect(sitemapXml(undefined, paths)).not.toContain('<loc>');
	});

	it.each([site, undefined])('is well-formed XML (site URL %s)', (url) => {
		const doc = new DOMParser().parseFromString(sitemapXml(url, paths), 'application/xml');
		expect(doc.querySelector('parsererror')).toBeNull();
		expect(doc.documentElement.tagName).toBe('urlset');
	});
});
