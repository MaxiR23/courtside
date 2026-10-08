// web/tests/lib/components/NextGameCard.test.ts
//
// Tests for the NextGameCard component.
//
// Tested:
// - Every line of the card: kicker, date, opponent, place and time
// - The tag only when present
// - Game center links to the game only when the game is linked
// - "Season over." with no next game
// - The live card: badge, clock, opponent, score, the five line values, Game center always linked
// - The live card with no line, with no next game, and in Spanish
//
// What is covered:
// - Each state the card shows
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NextGameCard.test.ts
//
// SEE: web/src/lib/components/NextGameCard.svelte
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import NextGameCard from '../../../src/lib/components/NextGameCard.svelte';
import type { LiveGameView } from '../../../src/lib/player/types';
import type { NextGameView } from '../../../src/lib/team/types';
import { preferLanguages } from '../../prefer-languages';

const game: NextGameView = {
	gameId: 'g-next',
	linked: true,
	tag: 'NBA Cup',
	date: 'Wednesday, October 7',
	opponent: '@ DEN',
	place: 'Ball Arena · Denver, CO',
	time: '7:30 PM ET · ESPN'
};

const gameHref = (id: string) => `/game/${id}` as never;

const live: LiveGameView = {
	gameId: 'g-live',
	opponent: '@ DEN',
	score: '78–74',
	clock: 'Q3 · 4:12',
	line: [
		{ label: 'MIN', value: '24:10', sub: null },
		{ label: 'PTS', value: '14', sub: null },
		{ label: 'REB', value: '4', sub: null },
		{ label: 'AST', value: '5', sub: null },
		{ label: 'FG', value: '7–15', sub: null }
	]
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('NextGameCard', () => {
	it('shows every line of the game', () => {
		render(NextGameCard, { props: { game, gameHref } });
		for (const text of [
			'Next game',
			'NBA Cup',
			'Wednesday, October 7',
			'@ DEN',
			'Ball Arena · Denver, CO',
			'7:30 PM ET · ESPN'
		]) {
			expect(screen.getByText(text)).toBeTruthy();
		}
	});

	it('shows no tag without one', () => {
		const { container } = render(NextGameCard, {
			props: { game: { ...game, tag: null }, gameHref }
		});
		expect(container.querySelector('.status-tag')).toBeNull();
	});

	it('links Game center to the game when it is linked', () => {
		render(NextGameCard, { props: { game, gameHref } });
		expect(screen.getByRole('link', { name: 'Game center' }).getAttribute('href')).toBe(
			'/game/g-next'
		);
	});

	it('has no link when the game is not linked', () => {
		render(NextGameCard, { props: { game: { ...game, linked: false }, gameHref } });
		expect(screen.queryByRole('link')).toBeNull();
	});

	it('shows Season over. with no next game', () => {
		render(NextGameCard, { props: { game: null, gameHref } });
		expect(screen.getByText('Season over.')).toBeTruthy();
		expect(screen.queryByText('Next game')).toBeNull();
	});
});

describe('NextGameCard live', () => {
	it('shows the badge, clock, opponent, score and the five line values', () => {
		render(NextGameCard, { props: { game, gameHref, live } });
		for (const text of ['LIVE', 'Q3 · 4:12', '@ DEN', '78–74', '24:10', '14', '4', '5', '7–15']) {
			expect(screen.getByText(text)).toBeTruthy();
		}
		expect(screen.getAllByRole('term').map((t) => t.textContent)).toEqual([
			'MIN',
			'PTS',
			'REB',
			'AST',
			'FG'
		]);
		expect(screen.queryByText('Next game')).toBeNull();
	});

	it('always links Game center to the live game', () => {
		render(NextGameCard, { props: { game: { ...game, linked: false }, gameHref, live } });
		expect(screen.getByRole('link', { name: 'Game center' }).getAttribute('href')).toBe(
			'/game/g-live'
		);
	});

	it('shows the muted line when the player has no line yet', () => {
		render(NextGameCard, { props: { game, gameHref, live: { ...live, line: null } } });
		expect(screen.getByText('Not in the game yet.')).toBeTruthy();
		expect(screen.queryByRole('term')).toBeNull();
	});

	it('takes precedence when there is no next game', () => {
		render(NextGameCard, { props: { game: null, gameHref, live } });
		expect(screen.queryByText('Season over.')).toBeNull();
		expect(screen.getByText('LIVE')).toBeTruthy();
	});

	it('shows the not-in-game line in Spanish', () => {
		preferLanguages(['es']);
		render(NextGameCard, { props: { game: null, gameHref, live: { ...live, line: null } } });
		expect(screen.getByText('Todavía no entró.')).toBeTruthy();
	});
});
