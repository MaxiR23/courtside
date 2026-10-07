// web/tests/lib/components/SeasonSeries.test.ts
//
// Tests for the SeasonSeries component.
//
// Tested:
// - The summary text
// - One row per game with date, "AWAY pts – pts HOME" and arena, in the given order
// - No rows on a first meeting
// - The current game row: "This game" in the accent, no points before tip-off, no dimmed side
// - The losing side of each completed game dimmed; a completed current game shows its points
//
// What is covered:
// - Each state
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SeasonSeries.test.ts
//
// SEE: web/src/lib/components/SeasonSeries.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import type { SeasonSeriesSection } from '../../../src/lib/game/types';

import SeasonSeries from '../../../src/lib/components/SeasonSeries.svelte';

const series: SeasonSeriesSection = {
	summary: 'GSW lead 2–1',
	meta: '3 of 4 games played',
	games: [
		{
			date: 'Jan 10',
			current: false,
			awayCode: 'GSW',
			awayPoints: 118,
			homePoints: 112,
			homeCode: 'LAL',
			loser: 'home',
			arena: 'Chase Center'
		},
		{
			date: 'Dec 2',
			current: false,
			awayCode: 'LAL',
			awayPoints: 121,
			homePoints: 109,
			homeCode: 'GSW',
			loser: 'home',
			arena: 'Crypto.com Arena'
		}
	]
};

describe('SeasonSeries', () => {
	it('shows the summary', () => {
		render(SeasonSeries, { props: { series } });
		expect(screen.getByText('GSW lead 2–1')).toBeTruthy();
	});

	it('shows one row per game with date, score line and arena, in order', () => {
		const { container } = render(SeasonSeries, { props: { series } });
		const rows = [...container.querySelectorAll('.game')].map((row) =>
			[...row.children].map((c) => c.textContent?.replace(/\s+/g, ' '))
		);
		expect(rows).toEqual([
			['Jan 10', 'GSW 118 – 112 LAL', 'Chase Center'],
			['Dec 2', 'LAL 121 – 109 GSW', 'Crypto.com Arena']
		]);
	});

	it('shows no rows on a first meeting', () => {
		const { container } = render(SeasonSeries, {
			props: { series: { summary: 'First meeting', meta: '0 of 4 games played', games: [] } }
		});
		expect(screen.getByText('First meeting')).toBeTruthy();
		expect(container.querySelectorAll('.game')).toHaveLength(0);
	});

	it('shows "This game" in the current game row with no points before tip-off', () => {
		const tonight: SeasonSeriesSection = {
			...series,
			games: [
				{
					date: 'This game',
					current: true,
					awayCode: 'LAL',
					awayPoints: null,
					homePoints: null,
					homeCode: 'GSW',
					loser: null,
					arena: 'Chase Center'
				}
			]
		};
		const { container } = render(SeasonSeries, { props: { series: tonight } });
		const row = container.querySelector('.game')!;
		expect([...row.children].map((c) => c.textContent?.replace(/\s+/g, ' '))).toEqual([
			'This game',
			'LAL – GSW',
			'Chase Center'
		]);
		expect(row.querySelector('.date')?.classList.contains('current')).toBe(true);
		expect(container.querySelector('.dimmed')).toBeNull();
	});

	it('dims the losing side of each completed game', () => {
		const { container } = render(SeasonSeries, { props: { series } });
		const dimmed = [...container.querySelectorAll('.dimmed')].map((d) =>
			d.textContent?.replace(/\s+/g, ' ')
		);
		expect(dimmed).toEqual(['112 LAL', '109 GSW']);
		expect(container.querySelector('.date.current')).toBeNull();
	});

	it('shows the points of a completed current game and dims its loser', () => {
		const final: SeasonSeriesSection = {
			...series,
			games: [
				{
					date: 'This game',
					current: true,
					awayCode: 'LAL',
					awayPoints: 100,
					homePoints: 105,
					homeCode: 'GSW',
					loser: 'away',
					arena: 'Chase Center'
				}
			]
		};
		const { container } = render(SeasonSeries, { props: { series: final } });
		expect(container.querySelector('.result')?.textContent?.replace(/\s+/g, ' ')).toBe(
			'LAL 100 – 105 GSW'
		);
		expect(container.querySelector('.dimmed')?.textContent).toBe('LAL 100');
	});
});
