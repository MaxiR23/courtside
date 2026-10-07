// web/tests/lib/components/SeasonSeries.test.ts
//
// Tests for the SeasonSeries component.
//
// Tested:
// - The summary text
// - One row per game with date, "AWAY pts – pts HOME" and arena, in the given order
// - No rows on a first meeting
// - No "Tonight" row and no dimmed side
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
			awayCode: 'GSW',
			awayPoints: 118,
			homePoints: 112,
			homeCode: 'LAL',
			arena: 'Chase Center'
		},
		{
			date: 'Dec 2',
			awayCode: 'LAL',
			awayPoints: 121,
			homePoints: 109,
			homeCode: 'GSW',
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

	it('draws no Tonight row and dims no side', () => {
		const { container } = render(SeasonSeries, { props: { series } });
		expect(screen.queryByText(/tonight/i)).toBeNull();
		expect(container.querySelector('.dimmed')).toBeNull();
	});
});
