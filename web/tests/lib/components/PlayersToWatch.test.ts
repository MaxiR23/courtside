// web/tests/lib/components/PlayersToWatch.test.ts
//
// Tests for the PlayersToWatch component.
//
// Tested:
// - Both cards, away first, with the team tag, first name, last name, team name and photo
// - The initials placeholder when a photo fails to load
//
// What is covered:
// - Each state and the photo error interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayersToWatch.test.ts
//
// SEE: web/src/lib/components/PlayersToWatch.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import type { PlayersSection } from '../../../src/lib/game/types';

import PlayersToWatch from '../../../src/lib/components/PlayersToWatch.svelte';

const players: PlayersSection = {
	away: {
		firstName: 'Stephen',
		lastName: 'Curry',
		teamCode: 'GSW',
		photo: '/away.svg',
		teamName: 'Golden State Warriors'
	},
	home: {
		firstName: 'LeBron',
		lastName: 'James',
		teamCode: 'LAL',
		photo: '/home.svg',
		teamName: 'Los Angeles Lakers'
	}
};

describe('PlayersToWatch', () => {
	it('shows both cards, away first, with tag, names, team name and photo', () => {
		const { container } = render(PlayersToWatch, { props: { players } });
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
		render(PlayersToWatch, { props: { players } });
		await fireEvent.error(screen.getByAltText('Stephen Curry'));
		expect(screen.getByRole('img', { name: 'Stephen Curry' }).textContent).toBe('SC');
		expect(screen.getByAltText('LeBron James')).toBeTruthy();
	});
});
