// web/tests/lib/components/NavRow.test.ts
//
// Tests for the NavRow component, the one nav drawn on every page.
//
// Tested:
// - Shows the logo mark image (/logo-mark.svg, alt empty, aria-hidden) before the brand name on both layouts; no square brand mark
// - Desktop: Games, Standings and a Tournaments button; no Cup, All-Star or Playoffs link while it is closed
// - Desktop Home: Games, Standings, Tournaments, the date and the Spoiler-free toggle, in that order
// - Tournaments: aria-expanded follows its state; it lists Cup, All-Star and Playoffs with their routes
// - Tournaments closes on Escape (focus back on the button), on a click outside and on selecting an item
// - Escape that closes the dropdown is defaultPrevented; a layout change closes the dropdown, the menu sheet and the calendar sheet and releases the scroll lock
// - Cup, All-Star and Playoffs pages: the Tournaments button is current and its matching item has aria-current; nothing else is
// - Tournaments is not current on Home, the standings page or a detail page
// - Home: Games is the current page; Standings is not
// - Detail pages: All games and Standings, nothing current, no date, no toggle
// - Standings page: Standings is the current page; All games is not
// - Links go to gamesHref and standingsHref
// - The mobile layout adds the mobile class
// - The search trigger is the last child of the desktop nav on every page
// - Mobile: the row holds the brand, the search trigger and the menu button, and nothing else
// - Mobile: the search trigger has its mobile class and opens the search overlay
// - Mobile menu sheet: its rows on Home and on other pages, the current page, a link closes it, Escape and Close close it with focus back on the menu button
// - Mobile menu sheet: the date row swaps to the calendar sheet; without a calendar it is a plain time
// - Mobile menu sheet: Spoiler-free toggles in place and keeps the sheet open, pressed state shown
// - Mobile menu sheet: mounted at the end of the body, outside the nav
// - Spoiler-free toggle: off by default, pressed when on, calls its callback
// - Spanish: Partidos, Clasificación, Torneos, Copa, All-Star, Playoffs, Sin spoilers, Todos los partidos, the mobile menu
// - With home.calendar the date is a button with aria-haspopup="dialog" in the same place; without it the date stays a plain time
// - With no selected day the sheet opens on the month of the date shown
// - Sources: the 48px sheet rows, the 44px dropdown items and menu button, the nav type tokens, the 22px logo mark through --brand-mark-size
//
// What is covered:
// - Every page state (home, standings, cup, all-star, playoffs, detail), both layouts, dropdown closed and open, sheet closed and open, with and without a calendar
// - A fixed date, no real clock
// - jsdom does not lay out: heights are asserted through the rules in the sources and the token values
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NavRow.test.ts
//
// SEE: web/src/lib/components/NavRow.svelte, web/src/lib/components/NavMenuSheet.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { formatDate } from '../../../src/lib/format/locale';
import { searchOverlay } from '../../../src/lib/search/overlay.svelte';
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
const mobileHome = { ...homeProps, layout: 'mobile' as const };
const dateOptions: Intl.DateTimeFormatOptions = {
	weekday: 'short',
	month: 'short',
	day: 'numeric',
	year: 'numeric'
};
const calendar = {
	load: undefined,
	season: 'current',
	selectedDay: '2026-10-04',
	today: '2026-10-04',
	windowDays: null,
	windowHref: (date: string) => `/?day=${date}` as ResolvedPathname,
	dayHref: (date: string) => `/day/${date}` as ResolvedPathname
};

const srcDir = join(import.meta.dirname, '../../../src/lib');
const source = (path: string): string => readFileSync(join(srcDir, path), 'utf8');

type Declaration = { property: string; value: string };
type Rule = { selectors: string[]; declarations: Declaration[] };

function styleOf(source: string): string {
	const match = source.match(/<style[^>]*>([\s\S]*?)<\/style>/);
	return (match?.[1] ?? '').replace(/\/\*[\s\S]*?\*\//g, '');
}

function rulesOf(style: string): Rule[] {
	const rules: Rule[] = [];
	for (const match of style.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
		const declarations = (match[2] ?? '')
			.split(';')
			.map((part) => part.trim())
			.filter((part) => part.includes(':'))
			.map((part) => {
				const index = part.indexOf(':');
				return {
					property: part.slice(0, index).trim().toLowerCase(),
					value: part.slice(index + 1).trim()
				};
			});
		const selectors = (match[1] ?? '').split(',').map((selector) => selector.trim());
		rules.push({ selectors, declarations });
	}
	return rules;
}

/** Whether a rule for the selector sets the property to the value. */
function sets(css: string, selector: string, property: string, value: string): boolean {
	return rulesOf(css).some(
		(rule) =>
			rule.selectors.includes(selector) &&
			rule.declarations.some((d) => d.property === property && d.value === value)
	);
}

afterEach(() => {
	vi.restoreAllMocks();
});

async function openTournaments(name = 'Tournaments') {
	await fireEvent.click(screen.getByRole('button', { name }));
}

async function openMenu(name = 'Open menu') {
	await fireEvent.click(screen.getByRole('button', { name }));
}

function sheetRows(): (string | undefined)[] {
	const dialog = screen.getByRole('dialog', { name: 'Menu' });
	return [...dialog.querySelectorAll('.row')].map((el) => el.textContent?.trim());
}

describe('NavRow with a calendar', () => {
	it('draws the date as a button that opens a dialog, before the toggle', () => {
		const { container } = render(NavRow, {
			props: { ...homeProps, home: { ...home, calendar } }
		});
		const button = screen.getByRole('button', { name: 'Open calendar' });
		expect(button.getAttribute('aria-haspopup')).toBe('dialog');
		expect(container.querySelector('time')?.getAttribute('datetime')).toBe('2026-10-04');
		const links = container.querySelector('.links') as HTMLElement;
		expect(links.children[3]?.contains(button)).toBe(true);
		expect(links.children[4]?.textContent?.trim()).toBe('Spoiler-free');
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

describe('NavRow on desktop', () => {
	it('shows the logo mark before the brand name, hidden from assistive technology', () => {
		const { container } = render(NavRow, { props: homeProps });
		expect(screen.getByText('Courtside')).toBeTruthy();
		const logo = container.querySelector('.brand img');
		expect(logo).not.toBeNull();
		expect(logo?.getAttribute('src')).toBe('/logo-mark.svg');
		expect(logo?.getAttribute('alt')).toBe('');
		expect(logo?.getAttribute('aria-hidden')).toBe('true');
		expect(container.querySelector('.brand')?.firstElementChild).toBe(logo);
		expect(logo?.nextElementSibling?.classList.contains('brand-name')).toBe(true);
		expect(container.querySelector('.brand-mark')).toBeNull();
	});

	it('shows Games, Standings and Tournaments, and no seasonal link while it is closed', () => {
		const { container } = render(NavRow, { props: standingsProps });
		const items = [...(container.querySelector('.links')?.children ?? [])].map((el) =>
			el.textContent?.trim()
		);
		expect(items).toEqual(['All games', 'Standings', 'Tournaments']);
		for (const name of ['Cup', 'All-Star', 'Playoffs']) {
			expect(screen.queryByRole('link', { name })).toBeNull();
		}
	});

	it('shows Games, Standings, Tournaments, the date and the toggle in order on Home', () => {
		const { container } = render(NavRow, { props: homeProps });
		const items = [...(container.querySelector('.links')?.children ?? [])].map((el) =>
			el.textContent?.trim()
		);
		expect(items).toEqual([
			'Games',
			'Standings',
			'Tournaments',
			'Sun, Oct 4, 2026',
			'Spoiler-free'
		]);
	});

	it('links Games to gamesHref and Standings to standingsHref', () => {
		render(NavRow, { props: homeProps });
		expect(screen.getByRole('link', { name: 'Games' }).getAttribute('href')).toBe('/#schedule');
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
	});

	it('reflects its state in aria-expanded and lists Cup, All-Star and Playoffs', async () => {
		render(NavRow, { props: homeProps });
		const button = screen.getByRole('button', { name: 'Tournaments' });
		expect(button.getAttribute('aria-expanded')).toBe('false');
		await fireEvent.click(button);
		expect(button.getAttribute('aria-expanded')).toBe('true');
		const links = ['Cup', 'All-Star', 'Playoffs'].map((name) => screen.getByRole('link', { name }));
		expect(links.map((l) => l.getAttribute('href'))).toEqual(['/cup', '/all-star', '/playoffs']);
		for (const link of links) expect(link.classList.contains('item')).toBe(true);
		await fireEvent.click(button);
		expect(button.getAttribute('aria-expanded')).toBe('false');
		expect(screen.queryByRole('link', { name: 'Cup' })).toBeNull();
	});

	it('closes the dropdown on Escape and returns focus to the button', async () => {
		render(NavRow, { props: homeProps });
		await openTournaments();
		await fireEvent.keyDown(window, { key: 'Escape' });
		const button = screen.getByRole('button', { name: 'Tournaments' });
		expect(document.activeElement).toBe(button);
		expect(screen.queryByRole('link', { name: 'Cup' })).toBeNull();
	});

	it('takes the Escape it closes the dropdown with, so the page does not see it', async () => {
		render(NavRow, { props: homeProps });
		await openTournaments();
		const event = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true });
		window.dispatchEvent(event);
		expect(event.defaultPrevented).toBe(true);
		const other = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true });
		window.dispatchEvent(other);
		expect(other.defaultPrevented).toBe(false);
	});

	it('closes the dropdown when the layout becomes mobile', async () => {
		const { rerender } = render(NavRow, { props: homeProps });
		await openTournaments();
		await rerender({ ...homeProps, layout: 'mobile' });
		expect(screen.queryByRole('link', { name: 'Cup' })).toBeNull();
		await rerender(homeProps);
		expect(screen.queryByRole('link', { name: 'Cup' })).toBeNull();
	});

	it('closes the menu sheet and releases the scroll lock when the layout becomes desktop', async () => {
		const { rerender } = render(NavRow, { props: mobileHome });
		await openMenu();
		expect(document.body.style.overflow).toBe('hidden');
		await rerender(homeProps);
		expect(screen.queryByRole('dialog', { name: 'Menu' })).toBeNull();
		expect(document.body.style.overflow).not.toBe('hidden');
	});

	it('closes the menu-owned calendar sheet and releases the scroll lock when the layout changes', async () => {
		const calendarHome = { ...mobileHome, home: { ...home, calendar } };
		const { rerender } = render(NavRow, { props: calendarHome });
		await openMenu();
		await fireEvent.click(screen.getByRole('button', { name: 'Open calendar' }));
		expect(screen.getByRole('dialog', { name: 'Calendar' })).toBeTruthy();
		await rerender({ ...calendarHome, layout: 'desktop' as const });
		expect(screen.queryByRole('dialog')).toBeNull();
		expect(document.body.style.overflow).not.toBe('hidden');
	});

	it('closes the dropdown on a click outside it and not on a click inside it', async () => {
		render(NavRow, { props: homeProps });
		await openTournaments();
		await fireEvent.click(screen.getByRole('list'));
		expect(screen.getByRole('link', { name: 'Cup' })).toBeTruthy();
		await fireEvent.click(document.body);
		expect(screen.queryByRole('link', { name: 'Cup' })).toBeNull();
	});

	it('closes the dropdown when an item is selected', async () => {
		render(NavRow, { props: homeProps });
		await openTournaments();
		const link = screen.getByRole('link', { name: 'Cup' });
		link.addEventListener('click', (event) => event.preventDefault());
		await fireEvent.click(link);
		expect(screen.queryByRole('link', { name: 'Cup' })).toBeNull();
	});

	it.each([
		['Cup', cupProps],
		['All-Star', allStarProps],
		['Playoffs', playoffsProps]
	])('marks Tournaments and %s current on its own page and nothing else', async (name, props) => {
		const { container } = render(NavRow, { props });
		const button = screen.getByRole('button', { name: 'Tournaments' });
		expect(button.classList.contains('current')).toBe(true);
		expect(button.getAttribute('aria-current')).toBeNull();
		await fireEvent.click(button);
		const link = screen.getByRole('link', { name });
		expect(link.getAttribute('aria-current')).toBe('page');
		expect(link.classList.contains('current')).toBe(true);
		expect(container.querySelectorAll('[aria-current]')).toHaveLength(1);
	});

	it('does not mark Tournaments current on Home, the standings page or a detail page', async () => {
		for (const props of [homeProps, standingsProps, detailProps]) {
			const { container, unmount } = render(NavRow, { props });
			const button = screen.getByRole('button', { name: 'Tournaments' });
			expect(button.classList.contains('current')).toBe(false);
			await fireEvent.click(button);
			for (const name of ['Cup', 'All-Star', 'Playoffs']) {
				const link = screen.getByRole('link', { name });
				expect(link.getAttribute('aria-current')).toBeNull();
				expect(link.classList.contains('current')).toBe(false);
			}
			expect(container.querySelectorAll('.item.current')).toHaveLength(0);
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
		rerender(mobileHome);
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

	it('ends the nav with the search trigger on every page', () => {
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

	it('shows Home in Spanish with a Spanish preference', async () => {
		preferLanguages(['es-ES']);
		render(NavRow, { props: homeProps });
		expect(screen.getByText(formatDate(today, dateOptions))).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Partidos' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Clasificación' })).toBeTruthy();
		await openTournaments('Torneos');
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
});

describe('NavRow on mobile', () => {
	it('holds only the brand, the search trigger and the menu button', () => {
		const { container } = render(NavRow, { props: mobileHome });
		const nav = container.querySelector('nav') as HTMLElement;
		const children = [...nav.children];
		expect(children).toHaveLength(3);
		expect(children[0]?.classList.contains('brand')).toBe(true);
		expect(children[0]?.querySelector('img')?.getAttribute('src')).toBe('/logo-mark.svg');
		expect(children[1]).toBe(screen.getByRole('button', { name: 'Search' }));
		const menu = screen.getByRole('button', { name: 'Open menu' });
		expect(children[2]).toBe(menu);
		expect(menu.classList.contains('menu-button')).toBe(true);
		expect(menu.getAttribute('aria-expanded')).toBe('false');
		expect(container.querySelector('.links')).toBeNull();
		expect(screen.queryByRole('link', { name: 'Games' })).toBeNull();
		expect(screen.queryByRole('button', { name: 'Spoiler-free' })).toBeNull();
	});

	it('gives the search trigger the mobile class and opens the search overlay', async () => {
		const show = vi.spyOn(searchOverlay, 'show').mockImplementation(() => {});
		render(NavRow, { props: mobileHome });
		const search = screen.getByRole('button', { name: 'Search' });
		expect(search.classList.contains('mobile')).toBe(true);
		await fireEvent.click(search);
		expect(show).toHaveBeenCalled();
	});

	it('opens a menu dialog with focus on Close and the rows in order on Home', async () => {
		render(NavRow, { props: { ...mobileHome, home: { ...home, calendar } } });
		await openMenu();
		const dialog = screen.getByRole('dialog', { name: 'Menu' });
		expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close' }));
		expect(screen.getByRole('button', { name: 'Open menu' }).getAttribute('aria-expanded')).toBe(
			'true'
		);
		expect(sheetRows()).toEqual([
			'Games',
			'Standings',
			'Cup',
			'All-Star',
			'Playoffs',
			'Sun, Oct 4, 2026',
			'Spoiler-free'
		]);
		expect(dialog.querySelector('button[aria-label="Open calendar"]')).not.toBeNull();
	});

	it('lists only the five links on other pages, with All games', async () => {
		render(NavRow, { props: { ...mobileHome, page: 'standings', home: undefined } });
		await openMenu();
		expect(sheetRows()).toEqual(['All games', 'Standings', 'Cup', 'All-Star', 'Playoffs']);
		expect(screen.queryByRole('button', { name: 'Spoiler-free' })).toBeNull();
	});

	it.each([
		['home', 'Games'],
		['standings', 'Standings'],
		['cup', 'Cup'],
		['playoffs', 'Playoffs']
	] as const)('marks only the current page in the sheet: %s', async (page, name) => {
		render(NavRow, { props: { ...mobileHome, page } });
		await openMenu();
		const dialog = screen.getByRole('dialog', { name: 'Menu' });
		const current = dialog.querySelectorAll('[aria-current]');
		expect(current).toHaveLength(1);
		expect(current[0]?.textContent?.trim()).toBe(name);
		expect(current[0]?.getAttribute('aria-current')).toBe('page');
	});

	it('closes the sheet when a link is selected', async () => {
		render(NavRow, { props: mobileHome });
		await openMenu();
		const link = screen.getByRole('link', { name: 'Cup' });
		expect(link.getAttribute('href')).toBe('/cup');
		link.addEventListener('click', (event) => event.preventDefault());
		await fireEvent.click(link);
		expect(screen.queryByRole('dialog', { name: 'Menu' })).toBeNull();
	});

	it('closes the sheet on Escape and returns focus to the menu button', async () => {
		render(NavRow, { props: mobileHome });
		await openMenu();
		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(screen.queryByRole('dialog', { name: 'Menu' })).toBeNull();
		expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Open menu' }));
	});

	it('closes the sheet on Close and returns focus to the menu button', async () => {
		render(NavRow, { props: mobileHome });
		await openMenu();
		await fireEvent.click(screen.getByRole('button', { name: 'Close' }));
		expect(screen.queryByRole('dialog', { name: 'Menu' })).toBeNull();
		expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Open menu' }));
	});

	it('swaps the menu for the calendar sheet from the date row, and focus returns to the menu button', async () => {
		render(NavRow, { props: { ...mobileHome, home: { ...home, calendar } } });
		await openMenu();
		await fireEvent.click(screen.getByRole('button', { name: 'Open calendar' }));
		expect(screen.queryByRole('dialog', { name: 'Menu' })).toBeNull();
		const sheet = screen.getByRole('dialog', { name: 'Calendar' });
		expect(sheet).toBeTruthy();
		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(screen.queryByRole('dialog', { name: 'Calendar' })).toBeNull();
		expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Open menu' }));
	});

	it('draws the date row as a plain time without a calendar', async () => {
		render(NavRow, { props: mobileHome });
		await openMenu();
		const dialog = screen.getByRole('dialog', { name: 'Menu' });
		expect(dialog.querySelector('time.row.date')).not.toBeNull();
		expect(screen.queryByRole('button', { name: 'Open calendar' })).toBeNull();
	});

	it('toggles Spoiler-free in place and keeps the sheet open', async () => {
		const onSpoilerFreeToggle = vi.fn();
		render(NavRow, { props: { ...mobileHome, home: { ...home, onSpoilerFreeToggle } } });
		await openMenu();
		await fireEvent.click(screen.getByRole('button', { name: 'Spoiler-free' }));
		expect(onSpoilerFreeToggle).toHaveBeenCalledTimes(1);
		expect(screen.getByRole('dialog', { name: 'Menu' })).toBeTruthy();
	});

	it('shows the pressed state of Spoiler-free in the sheet', async () => {
		render(NavRow, { props: { ...mobileHome, home: { ...home, spoilerFree: true } } });
		await openMenu();
		expect(screen.getByRole('button', { name: 'Spoiler-free' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
	});

	it('gives every sheet row the row class', async () => {
		render(NavRow, { props: mobileHome });
		await openMenu();
		const dialog = screen.getByRole('dialog', { name: 'Menu' });
		expect(dialog.querySelectorAll('.rows > li > .row')).toHaveLength(7);
	});

	it('mounts the sheet at the end of the body, outside the nav', async () => {
		const { container } = render(NavRow, { props: mobileHome });
		await openMenu();
		const dialog = screen.getByRole('dialog', { name: 'Menu' });
		expect(document.body.lastElementChild?.contains(dialog)).toBe(true);
		expect(container.querySelector('nav')?.contains(dialog)).toBe(false);
	});

	it('shows the menu in Spanish', async () => {
		preferLanguages(['es-ES']);
		render(NavRow, { props: mobileHome });
		await openMenu('Abrir menú');
		expect(screen.getByRole('dialog', { name: 'Menú' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Cerrar' })).toBeTruthy();
	});
});

describe('the nav sources', () => {
	const sheet = styleOf(source('components/NavMenuSheet.svelte'));
	const row = styleOf(source('components/NavRow.svelte'));
	const tokens = source('styles/tokens.css');

	it('gives the sheet rows 48px, the dropdown items and the menu button 44px', () => {
		expect(sets(sheet, '.row', 'min-height', 'var(--nav-sheet-row)')).toBe(true);
		expect(sets(row, '.item', 'min-height', 'var(--hit-target-size)')).toBe(true);
		expect(sets(row, '.menu-button', 'width', 'var(--hit-target-size)')).toBe(true);
		expect(sets(row, '.menu-button', 'height', 'var(--hit-target-size)')).toBe(true);
	});

	it('sizes the logo mark through --brand-mark-size and drops the inner square token', () => {
		expect(sets(row, '.brand-logo', 'width', 'var(--brand-mark-size)')).toBe(true);
		expect(sets(row, '.brand-logo', 'height', 'var(--brand-mark-size)')).toBe(true);
		expect(rulesOf(row).some((r) => r.selectors.some((s) => s.startsWith('.brand-mark')))).toBe(
			false
		);
		expect(tokens).toContain('--brand-mark-size: 22px;');
		expect(tokens).not.toContain('--brand-mark-inner-size');
	});

	it('sets the sizes through tokens', () => {
		for (const declaration of [
			'--nav-sheet-row: 48px;',
			'--hit-target-size: 44px;',
			'--brand-size: 16px;',
			'--nav-link-size: 14px;',
			'--nav-link-letter-spacing: 0.08em;'
		]) {
			expect(tokens).toContain(declaration);
		}
	});
});
