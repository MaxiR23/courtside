// web/tests/lib/components/Injuries.test.ts
//
// Tests for the Injuries component.
//
// Tested:
// - One column per team with its monogram (injury size), name and rows
// - The five statuses translated in English and Spanish, with a tone class
// - The comment as given, absent when null
// - The team monogram and name link to the team page; a player name links to its page, or is plain text with a null id
// - "No injuries reported." for a team with an empty list, in both languages
// - Only the league side renders when a side is null
//
// What is covered:
// - Each state, in both languages
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/Injuries.test.ts
//
// SEE: web/src/lib/components/Injuries.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { InjuriesSection, InjuryTagStatus } from '../../../src/lib/game/types';
import { preferLanguages } from '../../prefer-languages';

import Injuries from '../../../src/lib/components/Injuries.svelte';

afterEach(() => {
	vi.restoreAllMocks();
});

const statuses: [InjuryTagStatus, string, string][] = [
	['out', 'Out', 'Fuera'],
	['doubtful', 'Doubtful', 'Dudoso'],
	['questionable', 'Questionable', 'En duda'],
	['probable', 'Probable', 'Probable'],
	['day-to-day', 'Day-to-day', 'Día a día']
];
const injuries: InjuriesSection = {
	away: {
		code: 'GSW',
		name: 'Warriors',
		injuries: statuses.map(([status], i) => ({
			id: i === 1 ? null : `p${i}`,
			name: `Player ${i}`,
			status,
			comment: i === 0 ? 'Left knee soreness.' : null
		}))
	},
	home: { code: 'LAL', name: 'Lakers', injuries: [] }
};

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;
const props = { injuries, teamHref, playerHref };

describe('Injuries', () => {
	it('shows each team with its monogram at the injury size and its name', () => {
		const { container } = render(Injuries, { props });
		expect([...container.querySelectorAll('h3')].map((h) => h.textContent)).toEqual([
			'Warriors',
			'Lakers'
		]);
		const monograms = [...container.querySelectorAll('.team-monogram')];
		expect(monograms.map((e) => e.textContent)).toEqual(['GSW', 'LAL']);
		for (const monogram of monograms) expect(monogram.classList.contains('injury')).toBe(true);
	});

	it('shows each of the five statuses with its English label and tone class', () => {
		const { container } = render(Injuries, { props });
		const tags = [...container.querySelectorAll('.status-tag')];
		expect(tags.map((t) => t.textContent)).toEqual(statuses.map(([, en]) => en));
		tags.forEach((tag, i) => expect(tag.classList.contains(statuses[i][0])).toBe(true));
	});

	it('shows the five statuses in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		const { container } = render(Injuries, { props });
		expect([...container.querySelectorAll('.status-tag')].map((t) => t.textContent)).toEqual(
			statuses.map(([, , es]) => es)
		);
	});

	it('shows the comment as given and none when it is null', () => {
		const { container } = render(Injuries, { props });
		const comments = container.querySelectorAll('.comment');
		expect(comments).toHaveLength(1);
		expect(comments[0].textContent).toBe('Left knee soreness.');
	});

	it('shows "No injuries reported." for a team with no injuries', () => {
		render(Injuries, { props });
		expect(screen.getAllByText('No injuries reported.')).toHaveLength(1);
	});

	it('shows the empty message in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(Injuries, { props });
		expect(screen.getByText('Sin lesiones reportadas.')).toBeTruthy();
	});

	it('links the team monogram and name to the team page', () => {
		render(Injuries, { props });
		const links = screen.getAllByRole('link', { name: /GSW|Warriors/ });
		expect(links).toHaveLength(2);
		for (const link of links) expect(link.getAttribute('href')).toBe('/team/gsw');
	});

	it("links an injured player's name to the player page", () => {
		render(Injuries, { props });
		expect(screen.getByRole('link', { name: 'Player 0' }).getAttribute('href')).toBe('/player/p0');
	});

	it('shows the name as plain text when the player id is null', () => {
		render(Injuries, { props });
		expect(screen.getByText('Player 1')).toBeTruthy();
		expect(screen.queryByRole('link', { name: 'Player 1' })).toBeNull();
	});
});

describe('Injuries with a guest team', () => {
	it('renders only the league team', () => {
		const { container } = render(Injuries, {
			props: { injuries: { away: null, home: injuries.home }, teamHref, playerHref }
		});
		expect([...container.querySelectorAll('h3')].map((h) => h.textContent)).toEqual(['Lakers']);
	});
});
