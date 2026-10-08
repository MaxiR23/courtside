// web/tests/lib/components/BoxScore.test.ts
//
// Tests for the BoxScore component.
//
// Tested:
// - The away team is selected first, with its starters, bench and totals
// - The toggle switches to the home team; team names on desktop, codes on mobile
// - FG%, 3P% and FT% sit under the shooting columns in the totals
// - A positive plus-minus keeps its sign and is marked; zero and negative are not
// - A team with no bench shows no bench group
// - Each player name links to its player page, and the team toggle holds no link
// - The column labels in Spanish with a Spanish browser preference
//
// What is covered:
// - Both teams, both layouts, the empty bench and Spanish; layout (wrapping, sticky) is not asserted
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/BoxScore.test.ts
//
// SEE: web/src/lib/components/BoxScore.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import BoxScore from '../../../src/lib/components/BoxScore.svelte';
import type { BoxRow, BoxScoreSection, BoxScoreTeam } from '../../../src/lib/game/types';
import { preferLanguages } from '../../prefer-languages';

const row = (id: string, name: string, plusMinus: string, positive = false): BoxRow => ({
	id,
	name,
	minutes: '24:10',
	points: '20',
	fieldGoals: '8-15',
	threePoints: '2-6',
	freeThrows: '2-2',
	offensiveRebounds: '1',
	defensiveRebounds: '4',
	rebounds: '5',
	assists: '6',
	turnovers: '2',
	steals: '1',
	blocks: '0',
	fouls: '2',
	plusMinus,
	plusMinusPositive: positive
});

const totals = {
	points: '63',
	fieldGoals: '24-48',
	threePoints: '8-20',
	freeThrows: '7-9',
	offensiveRebounds: '5',
	defensiveRebounds: '25',
	rebounds: '30',
	assists: '18',
	turnovers: '9',
	steals: '5',
	blocks: '3',
	fouls: '12',
	fieldGoalPct: '50.0%',
	threePointPct: '40.0%',
	freeThrowPct: '77.8%'
};

const away: BoxScoreTeam = {
	code: 'LAL',
	name: 'Lakers',
	starters: [row('a1', 'LeBron James', '+4', true), row('a2', 'Anthony Davis', '0')],
	bench: [row('a3', 'Austin Reaves', '-3')],
	totals
};
const home: BoxScoreTeam = {
	code: 'GSW',
	name: 'Warriors',
	starters: [row('h1', 'Stephen Curry', '+2', true)],
	bench: [],
	totals: { ...totals, points: '62' }
};
const box: BoxScoreSection = { away, home };

const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;

const rowsText = (container: HTMLElement) =>
	[...container.querySelectorAll('.row')].map((r) => r.children[0].textContent?.trim());

describe('BoxScore', () => {
	it('selects the away team first and lists its starters, bench and totals', () => {
		const { container } = render(BoxScore, { props: { box, layout: 'desktop', playerHref } });
		expect(screen.getByRole('button', { name: 'Lakers' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(rowsText(container)).toEqual([
			'Player',
			'Starters',
			'LeBron James',
			'Anthony Davis',
			'Bench',
			'Austin Reaves',
			'Totals',
			''
		]);
	});

	it('switches to the home team when its toggle side is clicked', async () => {
		const { container } = render(BoxScore, { props: { box, layout: 'desktop', playerHref } });
		await fireEvent.click(screen.getByRole('button', { name: 'Warriors' }));
		expect(screen.getByRole('button', { name: 'Warriors' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(rowsText(container)).toContain('Stephen Curry');
		expect(rowsText(container)).not.toContain('LeBron James');
	});

	it('shows team names in the toggle on desktop and codes on mobile', () => {
		const desktop = render(BoxScore, { props: { box, layout: 'desktop', playerHref } });
		expect(
			[...desktop.container.querySelectorAll('.side')].map((b) => b.textContent?.trim())
		).toEqual(['Lakers', 'Warriors']);
		desktop.unmount();
		const mobile = render(BoxScore, { props: { box, layout: 'mobile', playerHref } });
		expect(
			[...mobile.container.querySelectorAll('.side')].map((b) => b.textContent?.trim())
		).toEqual(['LAL', 'GSW']);
	});

	it('shows FG%, 3P% and FT% under the shooting columns in the totals', () => {
		const { container } = render(BoxScore, { props: { box, layout: 'desktop', playerHref } });
		const percentages = container.querySelector('.percentages');
		const cells = [...(percentages?.children ?? [])].map((c) => c.textContent?.trim());
		// player, MIN, PTS, FG, 3PT, FT, then the rest
		expect(cells.slice(0, 7)).toEqual(['', '', '', '50.0%', '40.0%', '77.8%', '']);
		expect(cells).toHaveLength(15);
	});

	it('shows a positive plus-minus with its sign and marks it, zero and negative unmarked', () => {
		const { container } = render(BoxScore, { props: { box, layout: 'desktop', playerHref } });
		const cells = [...container.querySelectorAll('.plus-minus')];
		expect(cells.map((c) => c.textContent?.trim())).toEqual(['+4', '0', '-3']);
		expect(cells.map((c) => c.classList.contains('positive'))).toEqual([true, false, false]);
	});

	it('omits the bench group when the team has no bench players', async () => {
		const { container } = render(BoxScore, { props: { box, layout: 'desktop', playerHref } });
		await fireEvent.click(screen.getByRole('button', { name: 'Warriors' }));
		expect(rowsText(container)).not.toContain('Bench');
	});

	it('shows the column labels in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		const { container } = render(BoxScore, { props: { box, layout: 'desktop', playerHref } });
		const head = [...(container.querySelector('.head')?.children ?? [])].map((c) =>
			c.textContent?.trim()
		);
		expect(head).toEqual([
			'Jugador',
			'MIN',
			'PTS',
			'TC',
			'T3',
			'TL',
			'REBO',
			'REBD',
			'REB',
			'AST',
			'PÉR',
			'ROB',
			'TAP',
			'FP',
			'+/-'
		]);
		expect(screen.getByRole('group', { name: 'Equipo' })).toBeTruthy();
		expect(rowsText(container)).toContain('Titulares');
	});

	it('links each player name to its player page', () => {
		render(BoxScore, { props: { box, layout: 'desktop', playerHref } });
		expect(screen.getByRole('link', { name: 'LeBron James' }).getAttribute('href')).toBe(
			'/player/a1'
		);
		expect(screen.getByRole('link', { name: 'Austin Reaves' }).getAttribute('href')).toBe(
			'/player/a3'
		);
	});

	it('keeps the team toggle free of links', () => {
		const { container } = render(BoxScore, { props: { box, layout: 'desktop', playerHref } });
		expect(container.querySelectorAll('button a')).toHaveLength(0);
	});
});
