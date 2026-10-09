// web/tests/lib/components/PlayersToWatch.test.ts
//
// Tests for the PlayersToWatch component.
//
// Tested:
// - Both cards, away first, with the team tag, first name, last name, team name and photo
// - The star's name links to the player page; the team tag and name link to the team page
// - The initials placeholder when a photo fails to load
// - One card is rendered when a side is null (a guest team has no star)
//
// What is covered:
// - Each state and the photo error interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayersToWatch.test.ts
//
// SEE: web/src/lib/components/PlayersToWatch.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import type { PlayersSection } from '../../../src/lib/game/types';

import PlayersToWatch from '../../../src/lib/components/PlayersToWatch.svelte';

const players: PlayersSection = {
	away: {
		id: 'p-gsw',
		firstName: 'Stephen',
		lastName: 'Curry',
		teamCode: 'GSW',
		photo: '/away.svg',
		teamName: 'Golden State Warriors'
	},
	home: {
		id: 'p-lal',
		firstName: 'LeBron',
		lastName: 'James',
		teamCode: 'LAL',
		photo: '/home.svg',
		teamName: 'Los Angeles Lakers'
	}
};

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;
const props = { players, teamHref, playerHref };

describe('PlayersToWatch', () => {
	it('shows both cards, away first, with tag, names, team name and photo', () => {
		const { container } = render(PlayersToWatch, { props });
		const cards = container.querySelectorAll('.card');
		expect(cards).toHaveLength(2);
		const texts = [...cards].map((card) =>
			['.tag', '.first', '.last', '.team'].map((q) => card.querySelector(q)?.textContent)
		);
		expect(texts).toEqual([
			['GSW', 'Stephen', 'Curry', 'Golden State Warriors'],
			['LAL', 'LeBron', 'James', 'Los Angeles Lakers']
		]);
		expect(screen.getByAltText('Stephen Curry').getAttribute('src')).toBe('/away.svg');
		expect(screen.getByAltText('LeBron James').getAttribute('src')).toBe('/home.svg');
	});

	it('falls back to the initials placeholder when a photo fails to load', async () => {
		render(PlayersToWatch, { props });
		await fireEvent.error(screen.getByAltText('Stephen Curry'));
		expect(screen.getByRole('img', { name: 'Stephen Curry' }).textContent).toBe('SC');
		expect(screen.getByAltText('LeBron James')).toBeTruthy();
	});

	it("links each star's name to the player page", () => {
		render(PlayersToWatch, { props });
		expect(screen.getByRole('link', { name: 'Stephen Curry' }).getAttribute('href')).toBe(
			'/player/p-gsw'
		);
		expect(screen.getByRole('link', { name: 'LeBron James' }).getAttribute('href')).toBe(
			'/player/p-lal'
		);
	});

	it('links the team tag and team name to the team page', () => {
		render(PlayersToWatch, { props });
		for (const name of ['GSW', 'Golden State Warriors']) {
			expect(screen.getByRole('link', { name }).getAttribute('href')).toBe('/team/gsw');
		}
		expect(screen.getByRole('link', { name: 'LAL' }).getAttribute('href')).toBe('/team/lal');
	});
});

describe('PlayersToWatch with a guest team', () => {
	it('renders one card for the league side', () => {
		const { container } = render(PlayersToWatch, {
			props: { players: { away: null, home: players.home }, teamHref, playerHref }
		});
		expect(container.querySelectorAll('.card')).toHaveLength(1);
		expect(container.querySelector('.tag')?.textContent).toBe('LAL');
	});
});
