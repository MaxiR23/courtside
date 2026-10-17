// web/tests/lib/components/MatchupTeamBlock.test.ts
//
// Tests for the MatchupTeamBlock component.
//
// Tested:
// - The path: a row per game with W/L, opponent and score; a link only where the game page exists
// - The injuries, and the none line
// - The roster: number, name, position or the injury tag, PTS, REB and AST; a — for null averages
// - The starting five marks, one per starter, and the legend only when a starter exists
// - The leader values in the accent class
// - A click on a player calls onPlayer with the row index
// - A side with no team shows its label and no blocks; a null label draws no label (ADR 0054)
// - With a roster note: the path and the note, and no roster, injuries or none line
//
// What is covered:
// - Each state the block shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/MatchupTeamBlock.test.ts
//
// SEE: web/src/lib/components/MatchupTeamBlock.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it, vi } from 'vitest';

import MatchupTeamBlock from '../../../src/lib/components/MatchupTeamBlock.svelte';
import type { CupMatchupFeed } from '../../../src/lib/contract/cup-matchup';
import type { MatchupSideView } from '../../../src/lib/cup/types';
import { toMatchupView } from '../../../src/lib/feed/cup-matchup-props';

const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;

const feed = (): CupMatchupFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'cup-matchup.json'), 'utf8')
	) as CupMatchupFeed;

const sides = (source = feed()) => toMatchupView(source).sides;

const show = (side: MatchupSideView, onPlayer = () => {}) =>
	render(MatchupTeamBlock, { props: { side, gameHref, onPlayer } });

describe('MatchupTeamBlock path', () => {
	it('lists each game with W or L, the opponent and the score', () => {
		const { container } = show(sides()[0]);
		const rows = [...container.querySelectorAll('.path-row')];
		expect(rows.map((r) => r.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
			'W vs UXA 110-98',
			'L vs RXA 118-112',
			'W vs UXA 124-120'
		]);
	});

	it('links a game only where its page exists', () => {
		const { container } = show(sides()[0]);
		const rows = [...container.querySelectorAll('.path-row')];
		expect(rows.map((r) => r.tagName)).toEqual(['A', 'DIV', 'A']);
		expect(rows[0]?.getAttribute('href')).toBe('/game/9100001');
	});

	it('writes @ for an away game', () => {
		const { container } = show(sides()[1]);
		expect(container.querySelectorAll('.path-row')[0]?.textContent).toContain('@ TXA');
	});
});

describe('MatchupTeamBlock injuries', () => {
	it('shows the injuries of the side', () => {
		show(sides()[0]);
		expect(screen.getByText('Ankle sprain')).toBeTruthy();
	});

	it('shows the none line without injuries', () => {
		show(sides()[1]);
		expect(screen.getByText('No injuries reported.')).toBeTruthy();
	});
});

describe('MatchupTeamBlock roster', () => {
	it('shows one row per player with the stats, in the roster order', () => {
		const { container } = show(sides()[0]);
		const rows = [...container.querySelectorAll('tbody tr')];
		expect(rows).toHaveLength(5);
		const first = [...(rows[0]?.querySelectorAll('td') ?? [])].map((c) => c.textContent?.trim());
		expect(first).toEqual(['2', 'Ari Vance', 'G', '27.4', '5.1', '7.9']);
	});

	it('shows the injury tag in place of the position and a — for null averages', () => {
		const { container } = show(sides()[0]);
		const rows = [...container.querySelectorAll('tbody tr')];
		expect(rows[2]?.querySelector('.position')?.textContent?.trim()).toBe('Out');
		expect([...(rows[3]?.querySelectorAll('.stat') ?? [])].map((c) => c.textContent)).toEqual([
			'—',
			'—',
			'—'
		]);
	});

	it('marks each starter once and shows the legend', () => {
		show(sides()[0]);
		expect(screen.getAllByRole('img', { name: 'Starting five' })).toHaveLength(2);
		expect(screen.getAllByText('Starting five')).toHaveLength(1);
	});

	it('shows no legend and no mark without a starter', () => {
		const f = feed();
		for (const player of f.top.details?.roster ?? []) player.starter = false;
		show(sides(f)[0]);
		expect(screen.queryByText('Starting five')).toBeNull();
		expect(screen.queryAllByRole('img', { name: 'Starting five' })).toHaveLength(0);
	});

	it('puts the leader values in the accent class', () => {
		const { container } = show(sides()[0]);
		const rows = [...container.querySelectorAll('tbody tr')];
		const leaders = (row: Element | undefined) =>
			[...(row?.querySelectorAll('.stat') ?? [])].map((c) => c.classList.contains('leader'));
		expect(leaders(rows[0])).toEqual([true, false, true]);
		expect(leaders(rows[1])).toEqual([false, true, false]);
		expect(leaders(rows[4])).toEqual([false, false, false]);
	});

	it('calls onPlayer with the row index and the button on a click', async () => {
		const onPlayer = vi.fn();
		show(sides()[0], onPlayer);
		const button = screen.getByRole('button', { name: 'Bo Keller' });
		await fireEvent.click(button);
		expect(onPlayer).toHaveBeenCalledWith(1, button);
	});
});

describe('MatchupTeamBlock with no team', () => {
	it('shows the label and no path or roster', () => {
		const f = feed();
		f.bottom.team = null;
		f.bottom.details = null;
		const { container } = show(sides(f)[1]);
		expect(screen.getByText('To be decided')).toBeTruthy();
		expect(screen.getByText('Winner of West SF')).toBeTruthy();
		expect(container.querySelector('table')).toBeNull();
		expect(container.querySelector('.path')).toBeNull();
	});
});

describe('MatchupTeamBlock with a null label', () => {
	it('draws no label for a side with no team and no seed', () => {
		const f = feed();
		f.bottom.team = null;
		f.bottom.details = null;
		const side = { ...sides(f)[1], label: null };
		const { container } = show(side);
		expect(screen.getByText('To be decided')).toBeTruthy();
		expect(container.querySelector('.label')).toBeNull();
	});
});

describe('MatchupTeamBlock roster note', () => {
	const NOTE = 'Rosters are shown for the current season only';

	it('shows the path and the note in place of the injuries and the roster', () => {
		const { container } = render(MatchupTeamBlock, {
			props: { side: sides()[0], gameHref, onPlayer: () => {}, rosterNote: NOTE }
		});
		expect(container.querySelectorAll('.path-row').length).toBe(3);
		expect(screen.getByText(NOTE)).toBeTruthy();
		expect(screen.queryByRole('heading', { name: 'Roster' })).toBeNull();
		expect(container.querySelector('table')).toBeNull();
		expect(screen.queryByText('Ankle sprain')).toBeNull();
		expect(screen.queryByText('No injuries reported.')).toBeNull();
	});

	it('shows the roster and no note without it', () => {
		const { container } = show(sides()[0]);
		expect(screen.getByRole('heading', { name: 'Roster' })).toBeTruthy();
		expect(container.querySelector('table')).not.toBeNull();
		expect(screen.queryByText(NOTE)).toBeNull();
	});
});
