// web/tests/routes/preview/PagesPreview.test.ts
//
// Tests for the development-only catalog of every page, on both layouts.
//
// Tested:
// - Gives every entry a unique id anchor on its wrapper, with a level-2 title first
// - Shows every page in the desktop and the mobile layout
// - Shows each page header with its loading skeleton
// - Shows the page bodies of each page
// - Shows the playoffs with and without the champion hero
// - Shows the All-Star header before, live and after
// - Shows the season select on the pages that have one, in the header on desktop and full width on mobile
// - Uses no external URL and names no real source
//
// What is covered:
// - The states of the catalog: ready and loading, desktop and mobile. Only state, content
//   and classes are asserted: jsdom does not lay out, so the look is judged by eye
//
// Run with: cd web && pnpm exec vitest run tests/routes/preview/PagesPreview.test.ts
//
// SEE: web/src/routes/preview/PagesPreview.svelte
import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';

import PagesPreview from '../../../src/routes/preview/PagesPreview.svelte';

afterEach(() => localStorage.clear());

const layouts = ['desktop', 'mobile'];
const both = (base: string) => layouts.map((layout) => `${base}-${layout}`);

// The pages whose entry has a ready and a loading state.
const PAIRED = ['standings', 'team', 'player', 'day', 'game', 'series', 'cup'];
const READY = [
	...both('home-hero'),
	'home-body',
	...PAIRED.flatMap((page) => both(page)),
	...both('playoffs-picture'),
	...both('playoffs-champion'),
	...both('all-star-before'),
	...both('all-star-live'),
	...both('all-star-after')
];
const LOADING = [
	...both('home-hero-loading'),
	'home-body-loading',
	...PAIRED.flatMap((page) => both(`${page}-loading`)),
	...both('playoffs-loading'),
	...both('all-star-loading')
];
const IDS = [
	...both('home-hero'),
	...both('home-hero-loading'),
	'home-body',
	'home-body-loading',
	...['standings', 'team', 'player', 'day', 'game'].flatMap((page) => [
		...both(page),
		...both(`${page}-loading`)
	]),
	...both('playoffs-picture'),
	...both('playoffs-champion'),
	...both('playoffs-loading'),
	...['series', 'cup'].flatMap((page) => [...both(page), ...both(`${page}-loading`)]),
	...both('all-star-before'),
	...both('all-star-live'),
	...both('all-star-after'),
	...both('all-star-loading')
];

const entryIn = (container: HTMLElement, id: string): HTMLElement => {
	const entry = container.querySelector<HTMLElement>(`:scope > section[id="${id}"]`);
	if (!entry) throw new Error(`No entry ${id}`);
	return entry;
};
const sectionIds = (entry: Element, selector: string) =>
	[...entry.querySelectorAll(selector)].map((section) => section.id);
const text = (entry: Element) => entry.textContent?.replace(/\s+/g, ' ') ?? '';

// Each test renders the whole catalog, about 50 pages.
describe('page catalog', { timeout: 30_000 }, () => {
	it('gives every entry a unique id anchor on its wrapper', () => {
		const { container } = render(PagesPreview);
		const sections = [...container.querySelectorAll(':scope > section[id]')];
		const ids = sections.map((section) => section.id);
		expect(ids).toEqual(IDS);
		expect(new Set(ids).size).toBe(ids.length);
		expect(ids).toHaveLength(48);
		for (const section of sections) {
			expect(section.firstElementChild?.tagName).toBe('H2');
		}
	});

	it('shows every page in the desktop and the mobile layout', () => {
		const { container } = render(PagesPreview);
		for (const id of IDS.filter((id) => id.endsWith('-desktop'))) {
			const nav = entryIn(container, id).querySelector('nav.nav-row');
			expect(nav, id).toBeTruthy();
			expect(nav?.classList.contains('mobile'), id).toBe(false);
		}
		for (const id of IDS.filter((id) => id.endsWith('-mobile'))) {
			const nav = entryIn(container, id).querySelector('nav.nav-row');
			expect(nav?.classList.contains('mobile'), id).toBe(true);
			expect(entryIn(container, id).querySelector('.phone'), id).toBeTruthy();
		}
	});

	it('shows each page header with its loading skeleton', () => {
		const { container } = render(PagesPreview);
		for (const id of LOADING.filter((id) => id !== 'home-body-loading')) {
			expect(entryIn(container, id).querySelector('[aria-busy="true"]'), id).toBeTruthy();
		}
		for (const id of READY.filter((id) => id !== 'home-body')) {
			expect(entryIn(container, id).querySelector('[aria-busy="true"]'), id).toBeNull();
		}
		expect(entryIn(container, 'home-body-loading').querySelector('.bones')).toBeTruthy();
	});

	it('shows the page bodies of each page', () => {
		const { container } = render(PagesPreview);
		const at = (id: string) => entryIn(container, id);
		for (const layout of layouts) {
			expect(at(`standings-${layout}`).querySelector('[role="table"]')).toBeTruthy();
			expect(sectionIds(at(`cup-${layout}`), '.sections > section')).toEqual([
				'groups',
				'wild-card',
				'bracket',
				'games'
			]);
			expect(sectionIds(at(`playoffs-picture-${layout}`), '.sections > section')).toEqual([
				'picture',
				'bracket',
				'play-in',
				'leaders',
				'awards'
			]);
			expect(at(`team-${layout}`).querySelector('#overview')).toBeTruthy();
			expect(at(`player-${layout}`).querySelector('#profile')).toBeTruthy();
			expect(at(`game-${layout}`).querySelector('#score')).toBeTruthy();
			expect(at(`series-${layout}`).querySelectorAll('.games .cards > li')).toHaveLength(2);
		}
		expect(sectionIds(at('all-star-after-desktop'), '.sections > section')).toContain('mvp');
		expect(at('day-desktop').querySelectorAll('ul.games:not(.bones) > li')).toHaveLength(2);
		expect(at('home-body').querySelectorAll('.games > li')).toHaveLength(3);
	});

	it('shows the playoffs with and without the champion hero', () => {
		const { container } = render(PagesPreview);
		const champion = text(entryIn(container, 'playoffs-champion-desktop'));
		expect(champion).toContain('2027 NBA Champions');
		expect(champion).toContain('Owls');
		const picture = text(entryIn(container, 'playoffs-picture-desktop'));
		expect(picture).not.toContain('2027 NBA Champions');
		expect(picture).not.toContain('Won the series');
	});

	it('shows the All-Star header before, live and after', () => {
		const { container } = render(PagesPreview);
		expect(text(entryIn(container, 'all-star-before-desktop'))).toContain(
			'All-Star weekend is coming'
		);
		const live = text(entryIn(container, 'all-star-live-desktop'));
		expect(live).toContain('All-Star live now');
		expect(live).toContain('Live · Semifinals');
		const after = text(entryIn(container, 'all-star-after-desktop'));
		expect(after).toContain('All-Star recap');
		expect(after).toContain('25–23');
	});

	it('shows the season select on the pages that have one, in the header on desktop and full width on mobile', () => {
		const { container } = render(PagesPreview);
		const withSelect = IDS.filter((id) =>
			/^(standings|team|player|playoffs-(picture|champion|loading)|cup|all-star-(before|live|after|loading))-/.test(
				id
			)
		);
		expect(withSelect.length).toBeGreaterThan(0);
		for (const id of withSelect) {
			const select = entryIn(container, id).querySelector('header select[aria-label="Season"]');
			expect(select, id).toBeTruthy();
			expect(select?.classList.contains('full'), id).toBe(id.endsWith('-mobile'));
		}
		for (const id of IDS.filter((id) => !withSelect.includes(id))) {
			expect(entryIn(container, id).querySelector('select'), id).toBeNull();
		}
	});

	it('uses no external URL and names no real source', () => {
		const { container } = render(PagesPreview);
		const external = /^(https?:)?\/\//;
		for (const [selector, attribute] of [
			['img[src]', 'src'],
			['iframe[src]', 'src'],
			['a[href]', 'href']
		]) {
			for (const element of container.querySelectorAll(selector!)) {
				expect(element.getAttribute(attribute!)).not.toMatch(external);
			}
		}
		for (const code of ['GSW', 'LAL', 'BOS', 'NYK', 'DEN', 'PHX', 'OKC']) {
			expect(container.textContent).not.toMatch(new RegExp(`\\b${code}\\b`));
		}
	});
});
