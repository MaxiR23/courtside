// web/tests/lib/components/NavRow.test.ts
//
// Tests for the NavRow component, the one nav drawn on every page.
//
// Tested:
// - Shows the brand name and hides the brand mark from assistive technology
// - Home: Games, Standings, Cup, All-Star, Playoffs, the date and the Spoiler-free toggle, in that order
// - Home: Games is the current page; Standings is not
// - Detail pages: All games and Standings, nothing current, no date, no toggle
// - Standings page: Standings is the current page; All games is not
// - Links go to gamesHref and standingsHref; Cup goes to /cup
// - Cup page: Cup is the current page; Standings and All games are not; Cup is current nowhere else
// - The mobile layout adds the mobile class that puts the links on their own row
// - Playoffs goes to /playoffs; it is the current page on the playoffs page and nowhere else
// - The search trigger is the last child of the nav on Home, the detail pages, the standings page, the Cup page and the playoffs page
// - The mobile layout gives the search trigger its mobile class
// - Spoiler-free toggle: off by default, pressed when on, calls its callback
// - All-Star goes to /all-star; it is the current page on the All-Star page and nowhere else
// - Spanish: Partidos, Clasificación, Copa, All-Star, the date, Playoffs, Sin spoilers, Todos los partidos
// - With home.calendar the date is a button with aria-haspopup="dialog" in the same place; without it the date stays a plain time
// - With no selected day the sheet opens on the month of the date shown
//
// What is covered:
// - Every page state (home, standings, detail), both layouts, the toggle off and on, its click
// - A fixed date, no real clock
// - jsdom does not lay out: the mobile row is asserted through its class
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NavRow.test.ts
//
// SEE: web/src/lib/components/NavRow.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { formatDate } from '../../../src/lib/format/locale';
import { preferLanguages } from '../../prefer-languages';

import NavRow from '../../../src/lib/components/NavRow.svelte';

vi.mock('$app/navigation', () => ({ afterNavigate: () => {} }));

const today = new Date(2026, 9, 4, 12);
const gamesHref = '/#schedule' as ResolvedPathname;
const standingsHref = '/standings' as ResolvedPathname;
const home = { today, spoilerFree: false, onSpoilerFreeToggle: () => {} };
const homeProps = {
	page: 'home' as const,
	gamesHref,
	standingsHref,
	layout: 'desktop' as const,
	home
};
const detailProps = { ...homeProps, page: 'detail' as const, home: undefined };
const standingsProps = { ...homeProps, page: 'standings' as const, home: undefined };
const cupProps = { ...homeProps, page: 'cup' as const, home: undefined };
const allStarProps = { ...homeProps, page: 'all-star' as const, home: undefined };
const playoffsProps = { ...homeProps, page: 'playoffs' as const, home: undefined };
const dateOptions: Intl.DateTimeFormatOptions = {
	weekday: 'short',
	month: 'short',
	day: 'numeric',
	year: 'numeric'
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('NavRow with a calendar', () => {
	const calendar = {
		load: undefined,
		season: 'current',
		selectedDay: '2026-10-04',
		today: '2026-10-04',
		windowDays: null,
		windowHref: (date: string) => `/?day=${date}` as ResolvedPathname,
		dayHref: (date: string) => `/day/${date}` as ResolvedPathname
	};

	it('draws the date as a button that opens a dialog, before the toggle', () => {
		const { container } = render(NavRow, {
			props: { ...homeProps, home: { ...home, calendar } }
		});
		const button = screen.getByRole('button', { name: 'Open calendar' });
		expect(button.getAttribute('aria-haspopup')).toBe('dialog');
		expect(container.querySelector('time')?.getAttribute('datetime')).toBe('2026-10-04');
		const links = container.querySelector('.links') as HTMLElement;
		expect(links.children[5]?.contains(button)).toBe(true);
		expect(links.children[6]?.textContent?.trim()).toBe('Spoiler-free');
	});

	it('opens the sheet on the month of the date shown when no day is selected', async () => {
		const feed = JSON.parse(
			readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'calendar.json'), 'utf8')
		);
		const load = () => Promise.resolve({ ...feed, firstDay: '2026-09-01', lastDay: '2027-06-20' });
		render(NavRow, {
			props: { ...homeProps, home: { ...home, calendar: { ...calendar, load, selectedDay: null } } }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Open calendar' }));
		expect((await screen.findByRole('heading', { level: 2 })).textContent).toBe('October 2026');
	});

	it('keeps a plain time without a calendar', () => {
		const { container } = render(NavRow, { props: homeProps });
		expect(container.querySelector('time.date')).not.toBeNull();
		expect(screen.queryByRole('button', { name: 'Open calendar' })).toBeNull();
	});
});

describe('NavRow', () => {
	it('shows the brand name and hides the brand mark from assistive technology', () => {
		const { container } = render(NavRow, { props: homeProps });
		expect(screen.getByText('Courtside')).toBeTruthy();
		expect(container.querySelector('.brand-mark')?.getAttribute('aria-hidden')).toBe('true');
	});

	it('shows Games, Standings, Cup, All-Star, Playoffs, the date and the toggle in order on Home', () => {
		const { container } = render(NavRow, { props: homeProps });
		const items = Array.from(container.querySelector('.links')?.children ?? []).map((el) =>
			el.textContent?.trim()
		);
		expect(items).toEqual([
			'Games',
			'Standings',
			'Cup',
			'All-Star',
			'Playoffs',
			'Sun, Oct 4, 2026',
			'Spoiler-free'
		]);
	});

	it('links Games to gamesHref and Standings to standingsHref', () => {
		render(NavRow, { props: homeProps });
		expect(screen.getByRole('link', { name: 'Games' }).getAttribute('href')).toBe('/#schedule');
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
	});

	it('links Cup to /cup', () => {
		render(NavRow, { props: homeProps });
		expect(screen.getByRole('link', { name: 'Cup' }).getAttribute('href')).toBe('/cup');
	});

	it('links All-Star to /all-star', () => {
		render(NavRow, { props: homeProps });
		expect(screen.getByRole('link', { name: 'All-Star' }).getAttribute('href')).toBe('/all-star');
	});

	it('marks All-Star current on the All-Star page and nothing else', () => {
		const { container } = render(NavRow, { props: allStarProps });
		const link = screen.getByRole('link', { name: 'All-Star' });
		expect(link.getAttribute('aria-current')).toBe('page');
		expect(link.classList.contains('current')).toBe(true);
		expect(container.querySelectorAll('[aria-current]')).toHaveLength(1);
	});

	it('does not mark All-Star current on any other page', () => {
		for (const props of [homeProps, standingsProps, cupProps, playoffsProps, detailProps]) {
			const { unmount } = render(NavRow, { props });
			const link = screen.getByRole('link', { name: 'All-Star' });
			expect(link.getAttribute('aria-current')).toBeNull();
			expect(link.classList.contains('current')).toBe(false);
			unmount();
		}
	});

	it('links Playoffs to /playoffs', () => {
		render(NavRow, { props: homeProps });
		expect(screen.getByRole('link', { name: 'Playoffs' }).getAttribute('href')).toBe('/playoffs');
	});

	it('marks Playoffs current on the playoffs page and nothing else', () => {
		const { container } = render(NavRow, { props: playoffsProps });
		const playoffs = screen.getByRole('link', { name: 'Playoffs' });
		expect(playoffs.getAttribute('aria-current')).toBe('page');
		expect(playoffs.classList.contains('current')).toBe(true);
		expect(container.querySelectorAll('[aria-current]')).toHaveLength(1);
	});

	it('does not mark Playoffs current on Home, the standings page, the Cup page or a detail page', () => {
		for (const props of [homeProps, standingsProps, cupProps, detailProps]) {
			const { unmount } = render(NavRow, { props });
			const playoffs = screen.getByRole('link', { name: 'Playoffs' });
			expect(playoffs.getAttribute('aria-current')).toBeNull();
			expect(playoffs.classList.contains('current')).toBe(false);
			unmount();
		}
	});

	it('adds the mobile class on the playoffs page with the mobile layout', () => {
		const { container } = render(NavRow, { props: { ...playoffsProps, layout: 'mobile' } });
		expect(container.querySelector('nav')?.classList.contains('mobile')).toBe(true);
	});

	it('marks Cup current on the Cup page and neither Standings nor All games', () => {
		render(NavRow, { props: cupProps });
		const cup = screen.getByRole('link', { name: 'Cup' });
		expect(cup.getAttribute('aria-current')).toBe('page');
		expect(cup.classList.contains('current')).toBe(true);
		for (const name of ['Standings', 'All games']) {
			const link = screen.getByRole('link', { name });
			expect(link.getAttribute('aria-current')).toBeNull();
			expect(link.classList.contains('current')).toBe(false);
		}
	});

	it('does not mark Cup current on Home, the standings page or a detail page', () => {
		for (const props of [homeProps, standingsProps, detailProps]) {
			const { unmount } = render(NavRow, { props });
			const cup = screen.getByRole('link', { name: 'Cup' });
			expect(cup.getAttribute('aria-current')).toBeNull();
			expect(cup.classList.contains('current')).toBe(false);
			unmount();
		}
	});

	it('marks Games current on Home and not Standings', () => {
		render(NavRow, { props: homeProps });
		const games = screen.getByRole('link', { name: 'Games' });
		expect(games.getAttribute('aria-current')).toBe('page');
		expect(games.classList.contains('current')).toBe(true);
		const standings = screen.getByRole('link', { name: 'Standings' });
		expect(standings.getAttribute('aria-current')).toBeNull();
		expect(standings.classList.contains('current')).toBe(false);
	});

	it('shows All games and Standings on a detail page with nothing current', () => {
		const { container } = render(NavRow, { props: detailProps });
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/#schedule');
		expect(screen.getByRole('link', { name: 'Standings' })).toBeTruthy();
		expect(container.querySelector('[aria-current]')).toBeNull();
		expect(container.querySelector('time')).toBeNull();
		expect(screen.queryByRole('button', { name: 'Spoiler-free' })).toBeNull();
	});

	it('marks Standings current on the standings page and not All games', () => {
		render(NavRow, { props: standingsProps });
		const standings = screen.getByRole('link', { name: 'Standings' });
		expect(standings.getAttribute('aria-current')).toBe('page');
		expect(standings.classList.contains('current')).toBe(true);
		const all = screen.getByRole('link', { name: 'All games' });
		expect(all.getAttribute('aria-current')).toBeNull();
		expect(all.classList.contains('current')).toBe(false);
	});

	it('adds the mobile class only with the mobile layout', () => {
		const { container, rerender } = render(NavRow, { props: homeProps });
		expect(container.querySelector('nav')?.classList.contains('mobile')).toBe(false);
		rerender({ ...homeProps, layout: 'mobile' });
		expect(container.querySelector('nav')?.classList.contains('mobile')).toBe(true);
	});

	it('shows the Spoiler-free toggle off by default', () => {
		render(NavRow, { props: homeProps });
		expect(screen.getByRole('button', { name: 'Spoiler-free' }).getAttribute('aria-pressed')).toBe(
			'false'
		);
	});

	it('marks the toggle pressed when spoiler-free mode is on', () => {
		render(NavRow, { props: { ...homeProps, home: { ...home, spoilerFree: true } } });
		expect(screen.getByRole('button', { name: 'Spoiler-free' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
	});

	it('calls onSpoilerFreeToggle when the toggle is clicked', async () => {
		const onSpoilerFreeToggle = vi.fn();
		render(NavRow, { props: { ...homeProps, home: { ...home, onSpoilerFreeToggle } } });
		await fireEvent.click(screen.getByRole('button', { name: 'Spoiler-free' }));
		expect(onSpoilerFreeToggle).toHaveBeenCalledTimes(1);
	});

	it('shows Home in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(NavRow, { props: homeProps });
		expect(screen.getByText(formatDate(today, dateOptions))).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Partidos' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Clasificación' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Copa' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'All-Star' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Playoffs' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Sin spoilers' })).toBeTruthy();
	});

	it('shows All games in Spanish on a detail page', () => {
		preferLanguages(['es-ES']);
		render(NavRow, { props: detailProps });
		expect(screen.getByRole('link', { name: 'Todos los partidos' })).toBeTruthy();
	});

	it('ends the nav with the search trigger on Home, detail pages, the standings page, the Cup page and the playoffs page', () => {
		for (const props of [
			homeProps,
			detailProps,
			standingsProps,
			cupProps,
			allStarProps,
			playoffsProps
		]) {
			const { container, unmount } = render(NavRow, { props });
			const nav = container.querySelector('nav');
			expect(nav?.lastElementChild).toBe(screen.getByRole('button', { name: 'Search' }));
			unmount();
		}
	});

	it('gives the search trigger the mobile class with the mobile layout', () => {
		render(NavRow, { props: { ...homeProps, layout: 'mobile' } });
		expect(screen.getByRole('button', { name: 'Search' }).classList.contains('mobile')).toBe(true);
	});
});
