// web/tests/lib/components/TeamSchedule.test.ts
//
// Tests for the TeamSchedule component.
//
// Tested:
// - Month chips in feed order; the default group is pressed on load and its rows show
// - A click on another chip shows its rows and moves aria-pressed
// - A re-render with a feed lacking the selected group falls back to the default
// - The next row has the next class and the Next tag
// - A linked row is a link to the game and an unlinked row is not
// - Played and upcoming right columns; the mobile class
//
// What is covered:
// - Each state the section shows, plus the chip interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamSchedule.test.ts
//
// SEE: web/src/lib/components/TeamSchedule.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TeamSchedule from '../../../src/lib/components/TeamSchedule.svelte';
import type { ScheduleRowView, ScheduleSection } from '../../../src/lib/team/types';

const played = (gameId: string, linked: boolean): ScheduleRowView => ({
	gameId,
	linked,
	weekday: 'Thu',
	date: 'Oct 23',
	opponent: 'vs HOU',
	tags: [],
	next: false,
	outcome: { kind: 'played', result: 'win', resultLabel: 'W', score: '118–104', side: 'Home' }
});

const upcoming = (gameId: string, next: boolean, broadcast: string | null): ScheduleRowView => ({
	gameId,
	linked: false,
	weekday: 'Wed',
	date: 'Nov 5',
	opponent: '@ DEN',
	tags: next ? ['NBA Cup', 'Next'] : [],
	next,
	outcome: { kind: 'upcoming', time: '7:30 PM ET', broadcast }
});

const schedule: ScheduleSection = {
	groups: [
		{ key: '2025-10', label: 'Oct', rows: [played('g-won', true)] },
		{
			key: '2025-11',
			label: 'Nov',
			rows: [upcoming('g-next', true, 'Courtside TV'), upcoming('g-later', false, null)]
		},
		{ key: 'playoffs', label: 'Playoffs', rows: [played('g-po', false)] }
	],
	defaultKey: '2025-11'
};

const gameHref = (id: string) => `/game/${id}` as never;

const show = (value: ScheduleSection = schedule, layout: 'desktop' | 'mobile' = 'desktop') =>
	render(TeamSchedule, { props: { schedule: value, layout, gameHref } });

describe('TeamSchedule chips', () => {
	it('lists the chips in feed order with the default group pressed', () => {
		show();
		const chips = screen.getAllByRole('button');
		expect(chips.map((chip) => chip.textContent?.trim())).toEqual(['Oct', 'Nov', 'Playoffs']);
		expect(chips.map((chip) => chip.getAttribute('aria-pressed'))).toEqual([
			'false',
			'true',
			'false'
		]);
		expect(screen.getByRole('group', { name: 'Months' })).toBeTruthy();
		expect(screen.getAllByText('7:30 PM ET')).toHaveLength(2);
	});

	it('shows another group and moves aria-pressed on a click', async () => {
		const { container } = show();
		await fireEvent.click(screen.getByRole('button', { name: 'Oct' }));
		expect(screen.getByRole('button', { name: 'Oct' }).getAttribute('aria-pressed')).toBe('true');
		expect(screen.getByRole('button', { name: 'Nov' }).getAttribute('aria-pressed')).toBe('false');
		expect(container.querySelector('.outcome')?.textContent).toContain('118–104');
		expect(screen.queryByText('7:30 PM ET')).toBeNull();
	});

	it('falls back to the default group when the selected one leaves the feed', async () => {
		const { rerender } = show();
		await fireEvent.click(screen.getByRole('button', { name: 'Playoffs' }));
		await rerender({
			schedule: { ...schedule, groups: schedule.groups.slice(0, 2) },
			layout: 'desktop',
			gameHref
		});
		expect(screen.getByRole('button', { name: 'Nov' }).getAttribute('aria-pressed')).toBe('true');
	});

	it('keeps the selected group across a new feed that still has it', async () => {
		const { rerender } = show();
		await fireEvent.click(screen.getByRole('button', { name: 'Oct' }));
		await rerender({
			schedule: { ...schedule, defaultKey: 'playoffs' },
			layout: 'desktop',
			gameHref
		});
		expect(screen.getByRole('button', { name: 'Oct' }).getAttribute('aria-pressed')).toBe('true');
	});
});

describe('TeamSchedule rows', () => {
	it('tags and tints the next row', () => {
		const { container } = show();
		const next = container.querySelectorAll('.row.next');
		expect(next).toHaveLength(1);
		expect(next[0]?.textContent).toContain('Next');
		expect(next[0]?.textContent).toContain('NBA Cup');
	});

	it('links a row with detail to its game and leaves the others plain', async () => {
		show();
		expect(screen.queryByRole('link')).toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: 'Oct' }));
		expect(screen.getByRole('link').getAttribute('href')).toBe('/game/g-won');
	});

	it('shows the result and side of a played game', async () => {
		const { container } = show();
		await fireEvent.click(screen.getByRole('button', { name: 'Oct' }));
		expect(container.querySelector('.outcome')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
			'W 118–104 Home'
		);
		expect(container.querySelector('.win')?.textContent).toBe('W');
	});

	it('shows the time and broadcast of an upcoming game, with no broadcast when null', () => {
		const { container } = show();
		const outcomes = [...container.querySelectorAll('.outcome')].map((cell) =>
			cell.textContent?.replace(/\s+/g, ' ').trim()
		);
		expect(outcomes).toEqual(['7:30 PM ET Courtside TV', '7:30 PM ET']);
	});

	it('shows the weekday over the date and the opponent', () => {
		const { container } = show();
		expect(container.querySelector('.date')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
			'Wed Nov 5'
		);
		expect(screen.getAllByText('@ DEN')).toHaveLength(2);
	});

	it('uses the mobile class only with the mobile layout', () => {
		const { container, unmount } = show();
		expect(container.querySelector('.rows')?.classList.contains('mobile')).toBe(false);
		unmount();
		const mobile = show(schedule, 'mobile');
		expect(mobile.container.querySelector('.rows')?.classList.contains('mobile')).toBe(true);
	});
});
