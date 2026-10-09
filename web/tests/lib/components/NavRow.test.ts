// web/tests/lib/components/NavRow.test.ts
//
// Tests for the NavRow component, the one nav drawn on every page.
//
// Tested:
// - Shows the brand name and hides the brand mark from assistive technology
// - Home: Games, Standings, the date and the Spoiler-free toggle, in that order
// - Home: Games is the current page; Standings is not
// - Detail pages: All games and Standings, nothing current, no date, no toggle
// - Standings page: Standings is the current page; All games is not
// - Links go to gamesHref and standingsHref
// - The mobile layout adds the mobile class that puts the links on their own row
// - Spoiler-free toggle: off by default, pressed when on, calls its callback
// - Spanish: Partidos, Clasificación, the date, Sin spoilers, Todos los partidos
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
import { afterEach, describe, expect, it, vi } from 'vitest';

import { formatDate } from '../../../src/lib/format/locale';
import { preferLanguages } from '../../prefer-languages';

import NavRow from '../../../src/lib/components/NavRow.svelte';

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
const dateOptions: Intl.DateTimeFormatOptions = {
	weekday: 'short',
	month: 'short',
	day: 'numeric',
	year: 'numeric'
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('NavRow', () => {
	it('shows the brand name and hides the brand mark from assistive technology', () => {
		const { container } = render(NavRow, { props: homeProps });
		expect(screen.getByText('Courtside')).toBeTruthy();
		expect(container.querySelector('.brand-mark')?.getAttribute('aria-hidden')).toBe('true');
	});

	it('shows Games, Standings, the date and the toggle in order on Home', () => {
		const { container } = render(NavRow, { props: homeProps });
		const items = Array.from(container.querySelector('.links')?.children ?? []).map((el) =>
			el.textContent?.trim()
		);
		expect(items).toEqual(['Games', 'Standings', 'Sun, Oct 4, 2026', 'Spoiler-free']);
	});

	it('links Games to gamesHref and Standings to standingsHref', () => {
		render(NavRow, { props: homeProps });
		expect(screen.getByRole('link', { name: 'Games' }).getAttribute('href')).toBe('/#schedule');
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
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
		expect(screen.queryByRole('button')).toBeNull();
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
		expect(screen.getByRole('button', { name: 'Sin spoilers' })).toBeTruthy();
	});

	it('shows All games in Spanish on a detail page', () => {
		preferLanguages(['es-ES']);
		render(NavRow, { props: detailProps });
		expect(screen.getByRole('link', { name: 'Todos los partidos' })).toBeTruthy();
	});
});
