// web/tests/lib/components/DayHeader.test.ts
//
// Tests for the DayHeader component.
//
// Tested:
// - The date as the page title, and the season label with the weekday as the meta line
// - The previous and next arrows render only when their href is set, with the hrefs given
// - The calendar button renders when a calendar is given and not otherwise
// - The loading skeleton is busy and hidden from assistive technology; with no view and no loading only the nav row stays
// - Spanish arrow labels and calendar button with a Spanish browser preference
//
// What is covered:
// - The header drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/DayHeader.test.ts
//
// SEE: web/src/lib/components/DayHeader.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import DayHeader from '../../../src/lib/components/DayHeader.svelte';
import type { DayView } from '../../../src/lib/day/types';
import { preferLanguages } from '../../prefer-languages';

vi.mock('$app/navigation', () => ({ afterNavigate: () => {} }));

const view: DayView = {
	date: '1999-02-06',
	title: 'February 6, 1999',
	weekday: 'Saturday',
	seasonLabel: '1998-99',
	season: 1999,
	games: []
};
const calendar = {
	load: undefined,
	season: '1999',
	selectedDay: '1999-02-06',
	today: '2026-10-15',
	dayHref: (date: string) => `/day/${date}` as ResolvedPathname
};
const props = (changes: Record<string, unknown> = {}) => ({
	view,
	allGamesHref: '/' as ResolvedPathname,
	standingsHref: '/standings' as ResolvedPathname,
	previousHref: '/day/1999-02-05' as ResolvedPathname,
	nextHref: '/day/1999-02-07' as ResolvedPathname,
	calendar,
	layout: 'desktop' as const,
	...changes
});

afterEach(() => {
	vi.restoreAllMocks();
});

describe('DayHeader', () => {
	it('shows the date as the title and the season label with the weekday', () => {
		const { container } = render(DayHeader, { props: props() });
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('February 6, 1999');
		expect(container.querySelector('.meta')?.textContent).toBe('1998-99 · Saturday');
	});

	it('links the arrows to the days given', () => {
		render(DayHeader, { props: props() });
		expect(screen.getByRole('link', { name: 'Previous day' }).getAttribute('href')).toBe(
			'/day/1999-02-05'
		);
		expect(screen.getByRole('link', { name: 'Next day' }).getAttribute('href')).toBe(
			'/day/1999-02-07'
		);
	});

	it('hides an arrow whose href is null', () => {
		render(DayHeader, { props: props({ previousHref: null }) });
		expect(screen.queryByRole('link', { name: 'Previous day' })).toBeNull();
		expect(screen.getByRole('link', { name: 'Next day' })).toBeTruthy();
	});

	it('shows the calendar button only with a calendar', () => {
		const { unmount } = render(DayHeader, { props: props() });
		expect(screen.getByRole('button', { name: 'Calendar' }).getAttribute('aria-haspopup')).toBe(
			'dialog'
		);
		unmount();
		render(DayHeader, { props: props({ calendar: null }) });
		expect(screen.queryByRole('button', { name: 'Calendar' })).toBeNull();
	});

	it('shows a busy skeleton while loading', () => {
		const { container } = render(DayHeader, {
			props: props({
				view: null,
				loading: true,
				previousHref: null,
				nextHref: null,
				calendar: null
			})
		});
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.skeleton')?.getAttribute('aria-hidden')).toBe('true');
		expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
	});

	it('keeps only the nav row with no view and no loading', () => {
		const { container } = render(DayHeader, {
			props: props({ view: null, previousHref: null, nextHref: null, calendar: null })
		});
		expect(container.querySelector('nav')).not.toBeNull();
		expect(container.querySelector('.skeleton')).toBeNull();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
	});

	it('shows the arrows and the calendar button in Spanish for a Spanish browser', () => {
		preferLanguages(['es-ES']);
		render(DayHeader, { props: props() });
		expect(screen.getByRole('link', { name: 'Día anterior' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Día siguiente' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Calendario' })).toBeTruthy();
	});
});
