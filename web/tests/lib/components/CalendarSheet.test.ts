// web/tests/lib/components/CalendarSheet.test.ts
//
// Tests for the CalendarSheet component.
//
// Tested:
// - The season options equal the feed's seasons by label, in order; the dialog is named Calendar
// - It loads the season it is given and shows the selected day's month
// - Changing the select loads that season and shows its first month, or the selected day's month when the season holds it
// - A failed load shows the unavailable message and puts focus on Close
// - Focus moves to the select once the calendar loads
// - Close and Esc call onClose, on both layouts
// - The mobile layout is a modal dialog with a scrim that closes it and locks the scroll, and Shift+Tab from the season select wraps to the last focusable element; the desktop layout is not modal
// - A day of the calendar's window links to the home and any other day to its page; the games feed's days win over the window; no month after today's is offered (ADR 0054)
// - Spanish strings: Temporada, Cerrar and the weekday initials
//
// What is covered:
// - The sheet drawn from props with a fake loader and a recorded calendar; no fetch, no clock
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/CalendarSheet.test.ts
//
// SEE: web/src/lib/components/CalendarSheet.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import CalendarSheet from '../../../src/lib/components/CalendarSheet.svelte';
import type { CalendarFeed } from '../../../src/lib/contract/calendar';
import { preferLanguages } from '../../prefer-languages';

const recorded = (): CalendarFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'calendar.json'), 'utf8')
	) as CalendarFeed;

// The current season (2027) and 1999 from the recorded calendar.
const calendars = (): Record<string, CalendarFeed> => ({
	current: {
		...recorded(),
		season: 2027,
		seasonLabel: '2026-27',
		firstDay: '2026-10-20',
		lastDay: '2027-04-10',
		days: ['2026-10-18', '2026-10-19', '2026-10-20', '2027-04-10'],
		windowDays: ['2026-10-19', '2026-10-20']
	},
	'1999': recorded()
});

const calendar = (changes: Record<string, unknown> = {}) => {
	const feeds = calendars();
	const load = vi.fn((season: string) =>
		feeds[season] ? Promise.resolve(feeds[season]) : Promise.reject(new Error('down'))
	);
	return {
		load,
		season: 'current',
		selectedDay: '2026-10-20' as string | null,
		today: '2026-10-20',
		windowDays: null as string[] | null,
		windowHref: (date: string) => `/?day=${date}` as ResolvedPathname,
		dayHref: (date: string) => `/day/${date}` as ResolvedPathname,
		...changes
	};
};

const show = (
	changes: Record<string, unknown> = {},
	layout: 'desktop' | 'mobile' = 'desktop',
	onClose = vi.fn()
) => {
	const value = calendar(changes);
	const result = render(CalendarSheet, { props: { calendar: value, layout, onClose } });
	return { ...result, ...value, onClose };
};

afterEach(() => {
	vi.restoreAllMocks();
	document.body.style.overflow = '';
});

describe('CalendarSheet', () => {
	it('lists the seasons by label and shows the selected day month', async () => {
		const { load } = show();
		const select = (await screen.findByRole('combobox', { name: 'Season' })) as HTMLSelectElement;
		expect(load).toHaveBeenCalledWith('current');
		const labels = recorded().seasons.map((item) => item.seasonLabel);
		expect([...select.options].map((option) => option.textContent)).toEqual(labels);
		expect(screen.getByRole('dialog', { name: 'Calendar' })).toBeTruthy();
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('October 2026');
	});

	it("shows the new season's first month after a change", async () => {
		const { load } = show();
		const select = await screen.findByRole('combobox', { name: 'Season' });
		await fireEvent.change(select, { target: { value: '1999' } });
		await waitFor(() =>
			expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('February 1999')
		);
		expect(load).toHaveBeenLastCalledWith('1999');
	});

	it("shows the selected day's month when the new season holds it", async () => {
		show({ selectedDay: '1999-03-01' });
		const select = await screen.findByRole('combobox', { name: 'Season' });
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('October 2026');
		await fireEvent.change(select, { target: { value: '1999' } });
		await waitFor(() =>
			expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('March 1999')
		);
		expect(screen.getByRole('link', { name: 'March 1, 1999' }).getAttribute('aria-current')).toBe(
			'date'
		);
	});

	it('links a window day to the home and another day to its page', async () => {
		show();
		await screen.findByRole('combobox');
		expect(screen.getByRole('link', { name: 'October 20, 2026' }).getAttribute('href')).toBe(
			'/?day=2026-10-20'
		);
		expect(screen.getByRole('link', { name: 'October 18, 2026' }).getAttribute('href')).toBe(
			'/day/2026-10-18'
		);
	});

	it("uses the games feed's days over the calendar's window", async () => {
		show({ windowDays: ['2026-10-18'] });
		await screen.findByRole('combobox');
		expect(screen.getByRole('link', { name: 'October 18, 2026' }).getAttribute('href')).toBe(
			'/?day=2026-10-18'
		);
		expect(screen.getByRole('link', { name: 'October 20, 2026' }).getAttribute('href')).toBe(
			'/day/2026-10-20'
		);
	});

	it("offers no month after today's and draws no later day as a link", async () => {
		show();
		await screen.findByRole('combobox');
		expect((screen.getByRole('button', { name: 'Next month' }) as HTMLButtonElement).disabled).toBe(
			true
		);
		expect(screen.queryByRole('link', { name: 'April 10, 2027' })).toBeNull();
	});

	it('shows the unavailable message and focuses Close when the load fails', async () => {
		show({ season: '1850' });
		expect(
			await screen.findByText("Data isn't available right now. Check back later.")
		).toBeTruthy();
		expect(screen.queryByRole('combobox')).toBeNull();
		await waitFor(() =>
			expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close' }))
		);
	});

	it('shows the unavailable message with no loader', async () => {
		show({ load: undefined });
		expect(
			await screen.findByText("Data isn't available right now. Check back later.")
		).toBeTruthy();
	});

	it('moves focus to the select once the calendar loads', async () => {
		show();
		const select = await screen.findByRole('combobox', { name: 'Season' });
		await waitFor(() => expect(document.activeElement).toBe(select));
	});

	it.each(['desktop', 'mobile'] as const)(
		'closes on Close and on Esc on the %s layout',
		async (layout) => {
			const { onClose } = show({}, layout);
			await screen.findByRole('combobox');
			await fireEvent.click(screen.getByRole('button', { name: 'Close' }));
			expect(onClose).toHaveBeenCalledTimes(1);
			await fireEvent.keyDown(window, { key: 'Escape' });
			expect(onClose).toHaveBeenCalledTimes(2);
		}
	);

	it('is a modal dialog with a scrim that closes it on mobile, and locks the scroll', async () => {
		const { container, onClose, unmount } = show({}, 'mobile');
		await screen.findByRole('combobox');
		expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBe('true');
		expect(document.body.style.overflow).toBe('hidden');
		await fireEvent.click(container.querySelector('.scrim') as HTMLElement);
		expect(onClose).toHaveBeenCalledTimes(1);
		unmount();
		expect(document.body.style.overflow).toBe('');
	});

	it('is not modal, has no scrim and does not lock the scroll on desktop', async () => {
		const { container } = show({}, 'desktop');
		await screen.findByRole('combobox');
		expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBeNull();
		expect(screen.getByRole('dialog').classList.contains('panel')).toBe(true);
		expect(container.querySelector('.scrim')).toBeNull();
		expect(document.body.style.overflow).toBe('');
	});

	it('keeps Shift+Tab inside the mobile sheet: from the season select it wraps to the last focusable element', async () => {
		show({}, 'mobile');
		const select = await screen.findByRole('combobox');
		await waitFor(() => expect(document.activeElement).toBe(select));
		const event = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, cancelable: true });
		window.dispatchEvent(event);
		expect(event.defaultPrevented).toBe(true);
		const links = screen.getAllByRole('link');
		expect(document.activeElement).toBe(links[links.length - 1]);
	});

	it('shows its strings in Spanish for a Spanish browser', async () => {
		preferLanguages(['es-ES']);
		const { container } = show();
		await screen.findByRole('combobox', { name: 'Temporada' });
		expect(screen.getByRole('button', { name: 'Cerrar' })).toBeTruthy();
		expect(screen.getByRole('dialog', { name: 'Calendario' })).toBeTruthy();
		expect([...container.querySelectorAll('.weekday')].map((el) => el.textContent).join(' ')).toBe(
			'D L M X J V S'
		);
	});
});
