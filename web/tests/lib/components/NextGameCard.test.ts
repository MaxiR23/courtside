// web/tests/lib/components/NextGameCard.test.ts
//
// Tests for the NextGameCard component.
//
// Tested:
// - Every line of the card: kicker, date, opponent, place and time
// - The tag only when present
// - Game center links to the game only when the game is linked
// - "Season over." with no next game
//
// What is covered:
// - Each state the card shows
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NextGameCard.test.ts
//
// SEE: web/src/lib/components/NextGameCard.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import NextGameCard from '../../../src/lib/components/NextGameCard.svelte';
import type { NextGameView } from '../../../src/lib/team/types';

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
