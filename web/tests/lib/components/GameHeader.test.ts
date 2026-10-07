// web/tests/lib/components/GameHeader.test.ts
//
// Tests for the GameHeader component.
//
// Tested:
// - The nav row: the brand and an All games link to the home; alone with no header
// - The skeleton under the nav row while loading, busy and hidden from assistive tech
// - The desktop row in every status: scheduled, delayed, postponed, canceled, live and final
// - The loser dimmed on a final game, on the block and on the score
// - The mobile rows: two team rows with "city · record" and the score; the time row before a game
// - The venue strip: the arena photo with its name over it, the bare grid without a photo; without a city, the arena name
//   alone in the caption and no sub-line under the Venue cell
// - Each team name in full, in its own level 1 heading
//
// What is covered:
// - Each state the header shows
// - Word breaking is CSS and jsdom does no layout: it is checked with a grep (see the plan)
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/GameHeader.test.ts
//
// SEE: web/src/lib/components/GameHeader.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import GameHeader from '../../../src/lib/components/GameHeader.svelte';
import type { GameHeaderView } from '../../../src/lib/game/types';
import type { RowLayout } from '../../../src/lib/schedule/types';

const HOME = '/' as ResolvedPathname;

const away = { code: 'LAL', name: 'Lakers', city: 'Los Angeles', record: '12–5' };
const home = { code: 'GSW', name: 'Warriors', city: 'Golden State', record: '10–7' };

const venue = {
	arena: 'Chase Center',
	city: 'San Francisco',
	photo: '/highlight-1.svg',
	cells: [
		{ label: 'Tip-off', value: '7:00 PM ET', sub: 'Wednesday, October 7' },
		{ label: 'Venue', value: 'Chase Center', sub: 'San Francisco' },
		{ label: 'Broadcast', value: 'Network One', sub: null }
	]
};

const scheduled: GameHeaderView = {
	layout: 'pre-game',
	status: { state: 'scheduled', text: 'Wednesday, October 7 · Chase Center' },
	away,
	home,
	center: {
		kind: 'tip-off',
		tipTime: '7:00',
		tipSuffix: 'PM ET',
		broadcast: 'Network One',
		delayed: false
	},
	venue
};

const live: GameHeaderView = {
	layout: 'live',
	status: { state: 'live', text: 'Q3 · 4:12 · Chase Center' },
	away,
	home,
	center: { kind: 'score', away: 63, home: 62, loser: null },
	venue: null
};

const final: GameHeaderView = {
	layout: 'final',
	status: { state: 'final', text: 'Final · Wednesday, October 7 · Chase Center' },
	away,
	home,
	center: { kind: 'score', away: 110, home: 98, loser: 'home' },
	venue: null
};

function show(header: GameHeaderView | null, layout: RowLayout = 'desktop', loading = false) {
	return render(GameHeader, { props: { header, allGamesHref: HOME, layout, loading } });
}

describe('GameHeader', () => {
	it('shows the brand and an All games link to the home in the nav row', () => {
		show(null);
		expect(screen.getByText('Courtside')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/');
	});

	it('shows only the nav row with no header', () => {
		const { container } = show(null);
		expect(container.querySelector('.status-line')).toBeNull();
		expect(container.querySelector('.skeleton')).toBeNull();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
		expect(screen.queryAllByRole('heading')).toHaveLength(0);
	});

	it('shows the skeleton with the nav row while loading', () => {
		const { container } = show(null, 'desktop', true);
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.skeleton')?.getAttribute('aria-hidden')).toBe('true');
		expect(container.querySelectorAll('.skeleton .bone').length).toBeGreaterThan(0);
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
	});

	it('shows a scheduled game on the desktop row with its tip time, broadcast and venue strip', () => {
		const { container } = show(scheduled);
		expect(screen.getByText('Wednesday, October 7 · Chase Center')).toBeTruthy();
		expect(container.querySelector('.tip-time')?.textContent).toBe('7:00 PM ET');
		expect(container.querySelector('.broadcast')?.textContent).toBe('Network One');
		expect(container.querySelectorAll('.cell')).toHaveLength(3);
		expect(screen.getByText('Tip-off')).toBeTruthy();
		expect(screen.getByText('Los Angeles')).toBeTruthy();
		expect(screen.getByText('12–5')).toBeTruthy();
		expect(container.querySelector('.status-tag')).toBeNull();
		expect(container.querySelector('.live-badge')).toBeNull();
	});

	it('shows the arena name alone in the caption and no sub-line under the Venue cell when the city is null', () => {
		const { container } = show({
			...scheduled,
			venue: {
				...venue,
				city: null,
				cells: venue.cells.map((cell) => (cell.label === 'Venue' ? { ...cell, sub: null } : cell))
			}
		});
		expect(container.querySelector('.caption .arena')?.textContent).toBe('Chase Center');
		expect(container.querySelector('.caption .arena-city')).toBeNull();
		const cell = [...container.querySelectorAll('.cell')].find(
			(c) => c.querySelector('.cell-label')?.textContent === 'Venue'
		);
		expect(cell?.querySelector('.cell-value')?.textContent).toBe('Chase Center');
		expect(cell?.querySelector('.cell-sub')).toBeNull();
		expect(cell?.textContent).not.toContain('·');
	});

	it('shows a delayed game with its tag and "Scheduled" before the time', () => {
		const { container } = show({
			...scheduled,
			status: { state: 'delayed', text: 'Wednesday, October 7 · Chase Center' },
			center: {
				kind: 'tip-off',
				tipTime: '7:00',
				tipSuffix: 'PM ET',
				broadcast: null,
				delayed: true
			}
		});
		expect(container.querySelector('.status-tag')?.textContent).toBe('Delayed');
		expect(screen.getByText('Scheduled')).toBeTruthy();
		expect(container.querySelector('.broadcast')).toBeNull();
	});

	it('shows postponed and canceled games with their tag and no time', () => {
		for (const [state, label] of [
			['postponed', 'Postponed'],
			['canceled', 'Canceled']
		] as const) {
			const { container, unmount } = show({
				...scheduled,
				status: { state, text: 'Wednesday, October 7 · Chase Center' },
				center: { kind: 'none' }
			});
			expect(container.querySelector('.status-tag')?.textContent).toBe(label);
			expect(container.querySelector('.tip-time')).toBeNull();
			expect(container.querySelector('.score')).toBeNull();
			unmount();
		}
	});

	it('shows a live game with the badge, the period text and the score', () => {
		const { container } = show(live);
		expect(container.querySelector('.live-badge')).not.toBeNull();
		expect(screen.getByText('Q3 · 4:12 · Chase Center')).toBeTruthy();
		const points = [...container.querySelectorAll('.points')].map((el) => el.textContent);
		expect(points).toEqual(['63', '62']);
		expect(container.querySelector('.dimmed')).toBeNull();
		expect(container.querySelector('.venue')).toBeNull();
	});

	it('shows a final game with the loser dimmed on its block and its score', () => {
		const { container } = show(final);
		expect(screen.getByText('Final · Wednesday, October 7 · Chase Center')).toBeTruthy();
		expect(container.querySelector('.team.home')?.classList.contains('dimmed')).toBe(true);
		expect(container.querySelector('.team.away')?.classList.contains('dimmed')).toBe(false);
		const [awayPoints, homePoints] = [...container.querySelectorAll('.points')];
		expect(awayPoints.classList.contains('dimmed')).toBe(false);
		expect(homePoints.classList.contains('dimmed')).toBe(true);
	});

	it('shows two team rows with city · record and the score on the mobile row', () => {
		const { container } = show(final, 'mobile');
		expect(container.querySelectorAll('.row')).toHaveLength(2);
		expect(container.querySelector('.scoreboard')).toBeNull();
		expect(screen.getByText('Los Angeles · 12–5')).toBeTruthy();
		expect(screen.getByText('Golden State · 10–7')).toBeTruthy();
		const [awayPoints, homePoints] = [...container.querySelectorAll('.points')];
		expect(awayPoints.textContent).toBe('110');
		expect(homePoints.textContent).toBe('98');
		const rows = container.querySelectorAll('.row');
		expect(rows[0].classList.contains('dimmed')).toBe(false);
		expect(rows[1].classList.contains('dimmed')).toBe(true);
	});

	it('adds the time row on the mobile pre-game row', () => {
		const { container } = show(scheduled, 'mobile');
		expect(container.querySelectorAll('.row')).toHaveLength(2);
		expect(container.querySelector('.tip-off.mobile .tip-time')?.textContent).toBe('7:00 PM ET');
		expect(container.querySelector('.broadcast')?.textContent).toBe('Network One');
		expect(container.querySelector('.points')).toBeNull();
	});

	it('shows the arena photo with its name over it, and the bare grid without a photo', () => {
		const { container, unmount } = show(scheduled);
		const img = container.querySelector('.photo-box img');
		expect(img?.getAttribute('src')).toBe('/highlight-1.svg');
		expect(img?.getAttribute('alt')).toBe('');
		expect(container.querySelector('.caption .arena')?.textContent).toBe('Chase Center');
		expect(container.querySelector('.caption .arena-city')?.textContent).toBe('San Francisco');
		expect(container.querySelector('.bare-grid')).toBeNull();
		unmount();
		const bare = show({ ...scheduled, venue: { ...venue, photo: null } });
		expect(bare.container.querySelector('.photo-box img')).toBeNull();
		expect(bare.container.querySelector('.caption')).toBeNull();
		expect(bare.container.querySelector('.bare-grid')).not.toBeNull();
	});

	it('renders each team name in full in its own heading', () => {
		for (const layout of ['desktop', 'mobile'] as const) {
			const { unmount } = show(
				{
					...live,
					away: { ...away, name: 'Timberwolves' },
					home: { ...home, name: 'Trail Blazers' }
				},
				layout
			);
			const names = screen.getAllByRole('heading', { level: 1 }).map((h) => h.textContent);
			expect(names).toEqual(['Timberwolves', 'Trail Blazers']);
			unmount();
		}
	});
});
