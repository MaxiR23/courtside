// web/tests/lib/components/PlayersToWatch.test.ts
//
// Tests for the PlayersToWatch component.
//
// Tested:
// - Both cards, away first, with the team tag, first name, last name, team name and photo
// - The star's name links to the player page; the team tag and name link to the team page
// - The initials placeholder when a photo fails to load
// - One card is rendered when a side is null (a guest team has no star)
// - Mobile: no columns, the photo is a cutout behind the texts through PlayerAvatar, from tokens
//
// What is covered:
// - Each state (desktop, mobile, a guest side) and the photo error interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayersToWatch.test.ts
//
// SEE: web/src/lib/components/PlayersToWatch.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

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
const props = { players, layout: 'desktop' as const, teamHref, playerHref };
const mobileProps = { ...props, layout: 'mobile' as const };

const source = (file: string) =>
	readFileSync(join(__dirname, '..', '..', '..', 'src', 'lib', 'components', file), 'utf8');

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
			props: {
				players: { away: null, home: players.home },
				layout: 'desktop',
				teamHref,
				playerHref
			}
		});
		expect(container.querySelectorAll('.card')).toHaveLength(1);
		expect(container.querySelector('.tag')?.textContent).toBe('LAL');
	});
});

describe('PlayersToWatch on mobile', () => {
	it('lays each card out without columns, with the photo as a cutout behind the texts', () => {
		const { container } = render(PlayersToWatch, { props: mobileProps });
		const cards = container.querySelectorAll('.card');
		expect(cards).toHaveLength(2);
		for (const card of cards) {
			expect(card.classList).toContain('mobile');
			expect(card.firstElementChild?.classList).toContain('cutout');
			expect(card.querySelector('.cutout .avatar.team-leader')).not.toBeNull();
			expect(card.querySelector('.text')).not.toBeNull();
			expect(card.querySelector('.photo')).toBeNull();
			expect(card.querySelector('.photo-frame')).toBeNull();
		}
		expect(
			[...container.querySelectorAll('.cutout img')].map((i) => i.getAttribute('src'))
		).toEqual(['/away.svg', '/home.svg']);
		expect(screen.getByAltText('Stephen Curry')).toBeTruthy();
	});

	it('keeps the texts on mobile', () => {
		const { container } = render(PlayersToWatch, { props: mobileProps });
		const texts = [...container.querySelectorAll('.card')].map((card) =>
			['.tag', '.first', '.last', '.team'].map((q) => card.querySelector(q)?.textContent)
		);
		expect(texts).toEqual([
			['GSW', 'Stephen', 'Curry', 'Golden State Warriors'],
			['LAL', 'LeBron', 'James', 'Los Angeles Lakers']
		]);
	});

	it('falls back to initials in the cutout when a photo fails to load', async () => {
		const { container } = render(PlayersToWatch, { props: mobileProps });
		await fireEvent.error(screen.getByAltText('Stephen Curry'));
		const fallback = container.querySelector('.cutout [role="img"]');
		expect(fallback?.getAttribute('aria-label')).toBe('Stephen Curry');
		expect(fallback?.textContent).toBe('SC');
	});

	it('renders one mobile card for a guest side', () => {
		const { container } = render(PlayersToWatch, {
			props: { ...mobileProps, players: { away: null, home: players.home } }
		});
		expect(container.querySelectorAll('.card.mobile')).toHaveLength(1);
	});

	it('has no mobile class on desktop', () => {
		const { container } = render(PlayersToWatch, { props });
		expect(container.querySelectorAll('.card.mobile')).toHaveLength(0);
		expect(container.querySelectorAll('.cutout')).toHaveLength(0);
		expect(container.querySelectorAll('.photo .photo-frame.star')).toHaveLength(2);
	});

	it('takes the mobile height, cutout width and glow from tokens', () => {
		const src = source('PlayersToWatch.svelte');
		for (const fragment of [
			'min-height: var(--team-leader-min-height-mobile)',
			'width: var(--star-card-cutout-width-mobile)',
			'background: var(--star-glow)',
			'grid-template-columns: 1fr;',
			'size="team-leader"',
			'grid-template-columns: 1fr 1fr',
			'min-height: var(--star-card-min-height)'
		]) {
			expect(src).toContain(fragment);
		}
	});
});
