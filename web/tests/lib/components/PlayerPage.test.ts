// web/tests/lib/components/PlayerPage.test.ts
//
// Tests for the PlayerPage component.
//
// Tested:
// - Ready: every section in order, the tab ids matching the section ids, the h2 texts, the mini name
// - A view with no milestones, game log or awards renders none of those sections or tabs
// - The live card replaces the next game card while live is set
// - "Season over." with no next game and no live
// - Loading: aria-busy and the section skeleton
// - Unavailable: the unavailable row; Not found: "Player not found." and two All games links
// - The footer in every state, no nested interactive element, Spanish
//
// What is covered:
// - Each page state, drawn from props with no fetch; the view comes from the recorded player feed
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayerPage.test.ts
//
// SEE: web/src/lib/components/PlayerPage.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import PlayerPage from '../../../src/lib/components/PlayerPage.svelte';
import type { PlayerFeed } from '../../../src/lib/contract/player';
import { toPlayerView } from '../../../src/lib/feed/player-props';
import type { PlayerPageState } from '../../../src/lib/player/types';
import { preferLanguages } from '../../prefer-languages';

const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;
const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;

const feed = (): PlayerFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'player.json'), 'utf8')
	) as PlayerFeed;

const show = (state: PlayerPageState, layout: 'desktop' | 'mobile' = 'desktop') =>
	render(PlayerPage, {
		props: { state, allGamesHref: HOME, standingsHref: STANDINGS, layout, gameHref }
	});

const ready = (source: PlayerFeed = feed()): PlayerPageState => ({
	kind: 'ready',
	view: toPlayerView(source)
});

const liveFeed = (): PlayerFeed => {
	const source = feed();
	source.live = {
		gameId: 'g-live',
		opponent: 'DEN',
		isHome: false,
		period: 3,
		clock: '4:12',
		teamScore: 78,
		opponentScore: 74,
		line: null
	};
	return source;
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('PlayerPage ready', () => {
	it('renders every section in order, matching the tabs', () => {
		const { container } = show(ready());
		const sectionIds = [...container.querySelectorAll('.sections > section')].map((s) => s.id);
		expect(sectionIds).toEqual([
			'profile',
			'averages',
			'seasons',
			'milestones',
			'game-log',
			'awards'
		]);
		const tabHrefs = screen
			.getAllByRole('link')
			.map((a) => a.getAttribute('href'))
			.filter((href) => href?.startsWith('#'));
		expect(tabHrefs).toEqual(sectionIds.map((id) => `#${id}`));
		expect(container.querySelector('.mini-score')?.textContent).toBe('#2 S. Gilgeous-Alexander');
	});

	it('renders the h1, the section heads and the footer', () => {
		const { container } = show(ready());
		expect(screen.getByRole('heading', { level: 1, name: 'Gilgeous-Alexander' })).toBeTruthy();
		expect([...container.querySelectorAll('h2')].map((h) => h.textContent)).toEqual([
			'Profile',
			'Per-game averages',
			'Season by season',
			'Milestones',
			'Game log',
			'Awards'
		]);
		expect(screen.getByText('Last 5 games')).toBeTruthy();
		expect(container.querySelector('footer')).toBeTruthy();
	});

	it('renders no milestones, game log or awards section, nor their tabs, without data', () => {
		const source = feed();
		source.milestones = null;
		source.gameLog = null;
		source.awards = [];
		const { container } = show(ready(source));
		expect([...container.querySelectorAll('.sections > section')].map((s) => s.id)).toEqual([
			'profile',
			'averages',
			'seasons'
		]);
		expect(screen.queryByRole('link', { name: 'Milestones' })).toBeNull();
		expect(screen.queryByRole('link', { name: 'Game log' })).toBeNull();
		expect(screen.queryByRole('link', { name: 'Awards' })).toBeNull();
	});

	it('shows the next game card while the team is not live', () => {
		show(ready());
		expect(screen.getByText('Next game')).toBeTruthy();
		expect(screen.queryByText('LIVE')).toBeNull();
	});

	it('shows the live card instead of the next game card while live is set', () => {
		show(ready(liveFeed()));
		expect(screen.queryByText('Next game')).toBeNull();
		expect(screen.getByText('LIVE')).toBeTruthy();
		expect(screen.getByText('Not in the game yet.')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Game center' }).getAttribute('href')).toBe(
			'/game/g-live'
		);
	});

	it('shows "Season over." with no next game and no live', () => {
		const source = feed();
		source.nextGame = null;
		show(ready(source));
		expect(screen.getByText('Season over.')).toBeTruthy();
	});

	it('has no interactive element inside another', () => {
		const { container } = show(ready());
		expect(container.querySelectorAll('a a, button a, a button')).toHaveLength(0);
	});

	it('renders in Spanish', () => {
		preferLanguages(['es']);
		const source = feed();
		source.nextGame = null;
		const { container } = show(ready(source));
		expect(screen.getByText('Temporada terminada.')).toBeTruthy();
		expect([...container.querySelectorAll('h2')][0]?.textContent).toBe('Perfil');
	});
});

describe('PlayerPage other states', () => {
	it('shows the loading skeleton and the footer', () => {
		const { container } = show({ kind: 'loading' });
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.section-skeleton')).not.toBeNull();
		expect(container.querySelector('footer')).toBeTruthy();
	});

	it('shows the unavailable row', () => {
		const { container } = show({ kind: 'unavailable' });
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
		expect(container.querySelector('footer')).toBeTruthy();
	});

	it('shows "Player not found." with two All games links', () => {
		const { container } = show({ kind: 'not-found' });
		expect(screen.getByText('Player not found.')).toBeTruthy();
		expect(screen.getAllByRole('link', { name: 'All games' })).toHaveLength(2);
		expect(container.querySelector('footer')).toBeTruthy();
	});
});
