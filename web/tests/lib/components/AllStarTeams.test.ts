// web/tests/lib/components/AllStarTeams.test.ts
//
// Tests for the AllStarTeams component.
//
// Tested:
// - One card per team: 2 (previous edition), 3 (after) and 4 (live)
// - The champion card is highlighted; the placement and the record show
// - The W/L rows with their score and OT
// - The roster tiles link to the player, carry the title and a league bar when the player has a league team
// - No team link and no color for an All-Star team
// - The mobile layout uses the mobile roster tile size
// - A team with no results has no result rows
//
// What is covered:
// - Each state a card shows, drawn from the recorded feeds
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarTeams.test.ts
//
// SEE: web/src/lib/components/AllStarTeams.svelte
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import AllStarTeams from '../../../src/lib/components/AllStarTeams.svelte';
import { playerHref, viewOf } from '../all-star/views';

const show = (teams = viewOf('after').teams, layout: 'desktop' | 'mobile' = 'desktop') =>
	render(AllStarTeams, { props: { teams, layout, playerHref } });

describe('AllStarTeams', () => {
	it('draws one card per team on a day of 2, 3 and 4 teams', () => {
		expect(
			show(viewOf('after', 'previous').teams).container.querySelectorAll('article')
		).toHaveLength(2);
		expect(show().container.querySelectorAll('article')).toHaveLength(3);
		expect(show(viewOf('live').teams).container.querySelectorAll('article')).toHaveLength(4);
	});

	it('highlights the champion card only', () => {
		const { container } = show();
		const cards = [...container.querySelectorAll('article')];
		expect(cards.map((c) => c.classList.contains('champion'))).toEqual([true, false, false]);
		expect(cards[0].querySelector('.sigla')?.classList.contains('winner')).toBe(true);
	});

	it('shows the name, the placement and the record', () => {
		const { container } = show();
		const peaks = container.querySelectorAll('article')[2];
		expect(peaks.querySelector('.name')?.textContent).toBe('Team Peaks');
		expect(peaks.querySelector('.placement')?.textContent).toBe('Eliminated in the Round Robin');
		expect(peaks.querySelector('.record')?.textContent).toBe('0–2');
	});

	it('draws a W or L square, the text and the score for each result', () => {
		const { container } = show();
		const rows = [...container.querySelectorAll('article')[2].querySelectorAll('.result')];
		expect(rows.map((r) => r.querySelector('.mark')?.textContent)).toEqual(['L', 'L']);
		expect(rows.map((r) => r.querySelector('.text')?.textContent)).toEqual([
			'Round Robin · vs STR · OT',
			'Round Robin · vs WAV'
		]);
		expect(rows.map((r) => r.querySelector('.score')?.textContent)).toEqual(['17–20', '19–22']);
		const wins = [...container.querySelectorAll('article')[0].querySelectorAll('.mark')];
		expect(wins.every((w) => w.classList.contains('win'))).toBe(true);
	});

	it('draws no result list for a team with no results', () => {
		const teams = viewOf('live').teams;
		const { container } = show(teams.map((t, i) => (i === 2 ? { ...t, results: [] } : t)));
		expect(container.querySelectorAll('article')[2].querySelector('.results')).toBeNull();
		expect(container.querySelectorAll('article')[0].querySelector('.results')).not.toBeNull();
	});

	it('links each roster tile to the player with its title and a league bar when placed', () => {
		const { container } = show();
		const tiles = [...container.querySelectorAll('article')[2].querySelectorAll('a.tile')];
		expect(tiles.map((t) => t.getAttribute('href'))).toEqual(['/player/3001', '/player/3002']);
		expect(tiles.map((t) => t.getAttribute('title'))).toEqual(['Eli Made-Up', 'Fay Sketch · HBR']);
		expect(tiles.map((t) => t.querySelector('.league-bar') !== null)).toEqual([false, true]);
	});

	it('draws no team link and no team color for an All-Star team', () => {
		const { container } = show();
		expect(container.querySelectorAll('a[href^="/team"]')).toHaveLength(0);
		expect(container.querySelector('.head [style]')).toBeNull();
	});

	it('uses the mobile roster tile with the mobile layout', () => {
		const { container } = show(undefined, 'mobile');
		expect(container.querySelector('.teams')?.classList.contains('mobile')).toBe(true);
		expect(container.querySelector('.avatar')?.classList.contains('allstar-roster-mobile')).toBe(
			true
		);
		const wide = show();
		expect(wide.container.querySelector('.avatar')?.classList.contains('allstar-roster')).toBe(
			true
		);
	});
});
