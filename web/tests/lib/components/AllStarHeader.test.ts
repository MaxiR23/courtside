// web/tests/lib/components/AllStarHeader.test.ts
//
// Tests for the AllStarHeader component.
//
// Tested:
// - Per state: the tag, the meta line, the kicker, the h1, the score, the stats, the buttons and the plate
// - The before rows with their values and with "To be confirmed"
// - The nav row marks All-Star current; the nav bar is raised with the All-Star background on both layouts
// - The buttons scroll to #games, #mvp and #last-time
// - The stats count up from zero and show the final values when the timeout ends; the Championship cell is not counted
// - Under reduced motion the final values show at once
// - The Season tag of a past season whose feed is unavailable, none while loading or without a tag
// - The skeleton while loading, and only the nav and the title without a header
// - The season tag when the header has one, with no live dot or live stats on an after header; the select on desktop and mobile (full), its onChange
// - No guest-rule text, headline, story or ticker
// - The first line is the hero copy, or the title with no header; the mobile side padding only on mobile
//
// What is covered:
// - Each state the header shows, drawn from the recorded feeds
// - Fake timers; no animation frame is asserted (docs/testing.md); jsdom does not lay out
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarHeader.test.ts
//
// SEE: web/src/lib/components/AllStarHeader.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LiveTick } from '../../../src/lib/all-star/live-tick.svelte';
import AllStarHeader from '../../../src/lib/components/AllStarHeader.svelte';
import { viewOf } from '../all-star/views';

const show = (
	name: 'before' | 'live' | 'after' | null,
	layout: 'desktop' | 'mobile' = 'desktop',
	loading = false
) =>
	render(AllStarHeader, {
		props: {
			header: name === null ? null : viewOf(name).header,
			loading,
			allGamesHref: '/' as ResolvedPathname,
			standingsHref: '/standings' as ResolvedPathname,
			layout,
			tick: new LiveTick(),
			onLive: () => {}
		}
	});

const motion = (reduced: boolean) =>
	vi.stubGlobal(
		'matchMedia',
		vi.fn(() => ({ matches: reduced, addEventListener: () => {}, removeEventListener: () => {} }))
	);

beforeEach(() => {
	vi.useFakeTimers();
	document.documentElement.style.setProperty('--playoffs-count-duration', '1.4s');
	document.documentElement.style.setProperty('--playoffs-count-timeout', '1.6s');
	motion(false);
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
	document.documentElement.removeAttribute('style');
	document.body.innerHTML = '';
});

describe('AllStarHeader, after', () => {
	it('shows the tag, the meta, the kicker, the champion and the score', () => {
		const { container } = show('after');
		expect(screen.getByText('All-Star 2027')).toBeTruthy();
		expect(screen.getByText('Feb 14 · Example Arena')).toBeTruthy();
		expect(screen.getByText('Champions of the day')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'Team Stripes' })).toBeTruthy();
		expect(container.querySelector('.score')?.textContent).toBe('25–23');
	});

	it('shows the four stats with the Championship in accent', () => {
		const { container } = show('after');
		const stats = [...container.querySelectorAll('.stat')].map((s) => [
			s.querySelector('dt')?.textContent,
			s.classList.contains('accent')
		]);
		expect(stats).toEqual([
			['Games', false],
			['Teams', false],
			['Championship', true],
			['Attendance', false]
		]);
	});

	it('counts the stats up from zero, shows the final values after the timeout, and never counts the score', async () => {
		const { container } = show('after');
		await vi.advanceTimersByTimeAsync(0);
		const values = () => [...container.querySelectorAll('.stat dd')].map((d) => d.textContent);
		expect(values()).toEqual(['0', '0', '25–23', '0']);
		await vi.advanceTimersByTimeAsync(1600);
		expect(values()).toEqual(['4', '3', '25–23', '18,500']);
	});

	it('counts the attendance as one grouped integer, never as separate digit runs', async () => {
		const { container } = show('after');
		await vi.advanceTimersByTimeAsync(700);
		const text = container.querySelectorAll('.stat dd')[3].textContent ?? '';
		expect(text).toMatch(/^\d{1,3}(,\d{3})*$/);
		const n = Number(text.replaceAll(',', ''));
		expect(n).toBeGreaterThan(0);
		expect(n).toBeLessThan(18500);
		await vi.advanceTimersByTimeAsync(1600);
		expect(container.querySelectorAll('.stat dd')[3].textContent).toBe('18,500');
	});

	it('groups the attendance with the locale separator while it counts', async () => {
		const { overwriteGetLocale } = await import('../../../src/lib/paraglide/runtime.js');
		overwriteGetLocale(() => 'es');
		try {
			const { container } = show('after');
			await vi.advanceTimersByTimeAsync(700);
			const text = container.querySelectorAll('.stat dd')[3].textContent ?? '';
			expect(text).toMatch(/^\d{1,3}(\.\d{3})*$/);
			expect(Number(text.replaceAll('.', ''))).toBeLessThan(18500);
		} finally {
			overwriteGetLocale(() => 'en');
		}
	});

	it('shows the final values at once under reduced motion', async () => {
		motion(true);
		const { container } = show('after');
		await vi.advanceTimersByTimeAsync(0);
		expect([...container.querySelectorAll('.stat dd')].map((d) => d.textContent)).toEqual([
			'4',
			'3',
			'25–23',
			'18,500'
		]);
		expect(vi.getTimerCount()).toBe(0);
	});

	it('draws the MVP plate on desktop and the MVP thumb beside the title on mobile', () => {
		expect(show('after').container.querySelector('.plate-column .plate.mvp')).not.toBeNull();
		const mobile = show('after', 'mobile').container;
		expect(mobile.querySelector('.headline a.mvp-thumb')?.getAttribute('href')).toBe('#mvp');
		expect(mobile.querySelector('.plate-column')).toBeNull();
		const headline = mobile.querySelector('.headline');
		expect(headline?.lastElementChild?.classList.contains('thumb')).toBe(true);
		expect(headline?.firstElementChild?.tagName).toBe('H1');
	});

	it('scrolls to the games and to the MVP from the buttons', async () => {
		for (const id of ['games', 'mvp']) {
			const section = document.createElement('section');
			section.id = id;
			document.body.append(section);
		}
		const scrolled: string[] = [];
		Element.prototype.scrollIntoView = vi.fn(function (this: Element) {
			scrolled.push(this.id);
		});
		show('after');
		await fireEvent.click(screen.getByRole('button', { name: 'Every game' }));
		await fireEvent.click(screen.getByRole('button', { name: 'All-Star MVP' }));
		expect(scrolled).toEqual(['games', 'mvp']);
		expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
			behavior: 'smooth',
			block: 'start'
		});
	});

	it('scrolls without smoothing under reduced motion', async () => {
		motion(true);
		const section = document.createElement('section');
		section.id = 'games';
		document.body.append(section);
		Element.prototype.scrollIntoView = vi.fn();
		show('after');
		await fireEvent.click(screen.getByRole('button', { name: 'Every game' }));
		expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
			behavior: 'auto',
			block: 'start'
		});
	});
});

describe('AllStarHeader, live', () => {
	it('shows the live kicker, All-Star as the title, no score and the live stats', () => {
		const { container } = show('live');
		expect(screen.getByText('Live now', { selector: '.copy > .kicker' })).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'All-Star' })).toBeTruthy();
		expect(container.querySelector('.score')).toBeNull();
		expect([...container.querySelectorAll('.stat dt')].map((d) => d.textContent)).toEqual([
			'Games today',
			'Final',
			'Live now',
			'Teams'
		]);
		expect(screen.getByRole('button', { name: 'Follow the games' })).toBeTruthy();
		expect(container.querySelector('.plate.live')).not.toBeNull();
	});
});

describe('AllStarHeader, before', () => {
	it('shows the next edition kicker, the three rows, no stats and the year plate', () => {
		const { container } = show('before');
		expect(screen.getByText('Next edition')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'All-Star' })).toBeTruthy();
		expect(
			[...container.querySelectorAll('.info-row')].map((r) =>
				r.textContent?.replace(/\s+/g, ' ').trim()
			)
		).toEqual(['Date Feb 14, 2027', 'Venue Example Arena, Exampleton', 'Format To be confirmed']);
		expect(container.querySelector('.stats')).toBeNull();
		expect(container.querySelector('.numeral')?.textContent).toBe('2027');
	});

	it('scrolls to the Last time section from Last edition', async () => {
		const section = document.createElement('section');
		section.id = 'last-time';
		document.body.append(section);
		const scrolled: string[] = [];
		Element.prototype.scrollIntoView = vi.fn(function (this: Element) {
			scrolled.push(this.id);
		});
		show('before');
		await fireEvent.click(screen.getByRole('button', { name: 'Last edition' }));
		expect(scrolled).toEqual(['last-time']);
	});
});

describe('AllStarHeader, nav and states', () => {
	it('marks All-Star current in the nav', async () => {
		show('after');
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		const link = screen.getByRole('link', { name: 'All-Star' });
		expect(link.getAttribute('aria-current')).toBe('page');
		expect(screen.getByRole('button', { name: 'Search' })).toBeTruthy();
	});

	it('raises the nav bar on both layouts and gives it the All-Star background', () => {
		for (const layout of ['desktop', 'mobile'] as const) {
			const { container, unmount } = show('after', layout);
			expect(container.querySelector('.nav-bar.raised')).not.toBeNull();
			expect(
				container
					.querySelector<HTMLElement>('header')
					?.style.getPropertyValue('--page-header-nav-bg')
			).toBe('var(--allstar-header-bg)');
			unmount();
		}
	});

	it('shows only the nav and the title without a header', () => {
		const { container } = show(null);
		expect(screen.getByRole('heading', { level: 1, name: 'All-Star' })).toBeTruthy();
		expect(container.querySelector('.bones')).toBeNull();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
	});

	it('shows the season tag of a past season with no header, and none while loading', () => {
		const props = {
			allGamesHref: '/' as ResolvedPathname,
			standingsHref: '/standings' as ResolvedPathname,
			layout: 'desktop' as const,
			tick: new LiveTick(),
			onLive: () => {}
		};
		const { container, unmount } = render(AllStarHeader, {
			props: { ...props, header: null, seasonTag: 'Season 2004-05' }
		});
		expect(container.querySelector('.season-line')?.textContent).toContain('Season 2004-05');
		unmount();
		const loading = render(AllStarHeader, {
			props: { ...props, header: null, loading: true, seasonTag: 'Season 2004-05' }
		});
		expect(loading.container.querySelector('.season-line')).toBeNull();
		loading.unmount();
		expect(show(null).container.querySelector('.season-line')).toBeNull();
	});

	it('shows the skeleton while loading', () => {
		const { container } = show(null, 'desktop', true);
		expect(container.querySelector('.bones')).not.toBeNull();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
	});

	it('writes no guest-rule text, headline, story or ticker', () => {
		for (const name of ['before', 'live', 'after'] as const) {
			const { container, unmount } = show(name);
			const text = container.textContent?.toLowerCase() ?? '';
			for (const word of ['guest', 'headline', 'story', 'ticker', 'record']) {
				expect(text.includes(word)).toBe(false);
			}
			unmount();
		}
	});
});

describe('AllStarHeader season selector and tag', () => {
	const seasonSelect = (onChange = vi.fn()) => ({
		seasons: [
			{ season: 2027, seasonLabel: '2026-27' },
			{ season: 2025, seasonLabel: '2024-25' }
		],
		value: 2027,
		onChange
	});

	const render_ = (extra: Record<string, unknown> = {}) =>
		render(AllStarHeader, {
			props: {
				header: { ...viewOf('after').header, seasonTag: 'Season 2024-25' },
				allGamesHref: '/' as ResolvedPathname,
				standingsHref: '/standings' as ResolvedPathname,
				layout: 'desktop' as const,
				tick: new LiveTick(),
				onLive: () => {},
				...extra
			}
		});

	it('draws the season tag and no live dot or live stat on an after header', () => {
		const { container } = render_();
		expect(screen.getByText('Season 2024-25')).toBeTruthy();
		expect(container.querySelector('.live-dot')).toBeNull();
		expect(container.textContent?.toLowerCase().includes('live')).toBe(false);
	});

	it('draws no season tag when the header has none', () => {
		render_({ header: viewOf('after').header });
		expect(screen.queryByText('Season 2024-25')).toBeNull();
	});

	it('draws the select on desktop and calls onChange with the end year', () => {
		const onChange = vi.fn();
		render_({ seasonSelect: seasonSelect(onChange) });
		const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
		expect(select.classList.contains('full')).toBe(false);
		select.value = '2025';
		select.dispatchEvent(new Event('change', { bubbles: true }));
		expect(onChange).toHaveBeenCalledWith(2025);
	});

	it('draws the select full width on mobile', () => {
		render_({ layout: 'mobile', seasonSelect: seasonSelect() });
		expect(screen.getByRole('combobox', { name: 'Season' }).classList.contains('full')).toBe(true);
	});

	it('draws no select without the prop', () => {
		render_();
		expect(screen.queryByRole('combobox')).toBeNull();
	});

	it('starts the content with the first line, and the mobile side padding only on mobile', () => {
		const side = (c: HTMLElement) =>
			c.querySelector<HTMLElement>('header')?.style.getPropertyValue('--page-header-side-padding');
		const a = show('live', 'mobile');
		expect(a.container.querySelector('.first-line > .copy')).not.toBeNull();
		expect(side(a.container)).toBe('var(--allstar-side-padding-mobile)');
		a.unmount();
		const b = show(null, 'mobile');
		expect(b.container.querySelector('.first-line > h1')).not.toBeNull();
		b.unmount();
		const c = show('live', 'desktop');
		expect(side(c.container)).toBe('');
	});
});
