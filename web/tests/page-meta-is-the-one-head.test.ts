// web/tests/page-meta-is-the-one-head.test.ts
//
// Guard test: the per-page head is written in one place, PageMeta.
//
// Tested:
// - Only PageMeta.svelte and the root layout contain <svelte:head>
// - The root layout's head holds no title, description, Open Graph, Twitter, canonical or robots tag
// - Every +page.svelte under web/src/routes (preview included) renders <PageMeta
// - Only lib/meta/head.ts names og: or twitter:card
// - The matchers flag the real forms and pass look-alikes
//
// What is covered:
// - Happy path (the code complies), edge cases (spacing, look-alikes) and the error case
//   (a stray head is flagged with its file)
// - The scan cannot pass on an empty file list
//
// Run with: cd web && pnpm exec vitest run tests/page-meta-is-the-one-head.test.ts
//
// SEE: web/src/lib/components/PageMeta.svelte, web/src/lib/meta/head.ts
import { readdirSync, readFileSync } from 'node:fs';
import { join, sep } from 'node:path';
import { describe, expect, it } from 'vitest';

const srcDir = join(import.meta.dirname, '../src');
const paraglideDir = join('lib', 'paraglide');
const pageMeta = join('lib', 'components', 'PageMeta.svelte');
const layout = join('routes', '+layout.svelte');
const builder = join('lib', 'meta', 'head.ts');

const files = readdirSync(srcDir, { recursive: true, encoding: 'utf8' }).filter(
	(path) => /\.(svelte|ts)$/.test(path) && !path.startsWith(paraglideDir + sep)
);
const svelteFiles = files.filter((path) => path.endsWith('.svelte'));
const pages = svelteFiles.filter((path) => path.endsWith('+page.svelte'));

const opensHead = (text: string): boolean => /<svelte:head(\s|>|\/)/.test(text);
const headTag = (text: string): boolean =>
	/<title|name="description"|property="og:|name="twitter:|rel="canonical"|name="robots"/.test(text);
const rendersPageMeta = (text: string): boolean => /<PageMeta(\s|\/|>)/.test(text);
const namesSocialTags = (text: string): boolean => /\bog:|twitter:card/.test(text);

const read = (file: string) => readFileSync(join(srcDir, file), 'utf8');

describe('the page head', () => {
	it('finds the files to scan, so the scan cannot pass on an empty list', () => {
		expect(files.length).toBeGreaterThan(100);
		expect(svelteFiles).toContain(pageMeta);
		expect(svelteFiles).toContain(layout);
		expect(pages.length).toBeGreaterThan(10);
		expect(pages).toContain(join('routes', 'preview', '+page.svelte'));
	});

	it('flags a head and passes look-alikes', () => {
		expect(opensHead('<svelte:head>')).toBe(true);
		expect(opensHead('<svelte:head >')).toBe(true);
		expect(opensHead('<svelte:head><title>x</title>')).toBe(true);
		expect(opensHead('<svelte:headless>')).toBe(false);
		expect(headTag('<meta property="og:title" content="x" />')).toBe(true);
		expect(headTag('<link rel="canonical" href="/" />')).toBe(true);
		expect(headTag('<link rel="icon" href="/favicon.ico" />')).toBe(false);
		expect(rendersPageMeta('<PageMeta noindex />')).toBe(true);
		expect(rendersPageMeta('<PageMetaX />')).toBe(false);
		expect(namesSocialTags('twitter:card')).toBe(true);
		expect(namesSocialTags('prefix:cardinal')).toBe(false);
		expect(namesSocialTags('Game log: 5')).toBe(false);
	});

	it('writes <svelte:head> only in PageMeta and the root layout', () => {
		for (const file of svelteFiles.filter((f) => f !== pageMeta && f !== layout)) {
			expect(opensHead(read(file)), `${file} writes its own <svelte:head>`).toBe(false);
		}
	});

	it('keeps the root layout head to the icon and fonts', () => {
		const head = read(layout).match(/<svelte:head[\s\S]*?<\/svelte:head>/)?.[0] ?? '';
		expect(head).not.toBe('');
		expect(headTag(head), 'the root layout head holds a per-page tag').toBe(false);
	});

	it('renders PageMeta in every route page', () => {
		for (const file of pages) {
			expect(rendersPageMeta(read(file)), `${file} does not render <PageMeta`).toBe(true);
		}
	});

	it('names Open Graph and Twitter tags only in the builder', () => {
		for (const file of files.filter((f) => f !== builder)) {
			expect(namesSocialTags(read(file)), `${file} names a social tag`).toBe(false);
		}
	});
});
