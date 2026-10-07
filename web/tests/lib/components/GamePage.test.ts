// web/tests/lib/components/GamePage.test.ts
//
// Tests for the GamePage component.
//
// Tested:
// - Loading: the header skeleton and two section skeletons, busy and hidden from assistive tech
// - Feed unavailable: the nav row and the data unavailable row
// - Unknown game: the nav row and "Game not found." with a link to all games
// - Ready: the header and the tabs; a postponed game in the pre-game layout with its status tag
// - The footer in every state
// - The not-found row in Spanish with a Spanish browser preference
//
// What is covered:
// - Each page state, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/GamePage.test.ts
//
// SEE: web/src/lib/components/GamePage.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import GamePage from '../../../src/lib/components/GamePage.svelte';
import type { GamePageState, GameView } from '../../../src/lib/game/types';
import { preferLanguages } from '../../prefer-languages';

const HOME = '/' as ResolvedPathname;

const team = (code: string, name: string, city: string, record: string) => ({
	code,
	name,
	city,
	record
});

const view: GameView = {
	header: {
		layout: 'live',
		status: { state: 'live', text: 'Q3 · 4:12 · Chase Center' },
		away: team('LAL', 'Lakers', 'Los Angeles', '12–5'),
		home: team('GSW', 'Warriors', 'Golden State', '10–7'),
		center: { kind: 'score', away: 63, home: 62, loser: null },
		venue: null
	},
	tabs: [
		{ id: 'score', label: 'Score' },
		{ id: 'injuries', label: 'Injuries' }
	],
	miniScore: { awayCode: 'LAL', away: 63, home: 62, homeCode: 'GSW' }
};

const postponed: GameView = {
	header: {
		layout: 'pre-game',
		status: { state: 'postponed', text: 'Wednesday, October 7 · Chase Center' },
		away: view.header.away,
		home: view.header.home,
		center: { kind: 'none' },
		venue: {
			arena: 'Chase Center',
			city: 'San Francisco',
			photo: null,
			cells: [{ label: 'Venue', value: 'Chase Center', sub: 'San Francisco' }]
		}
	},
	tabs: [],
	miniScore: null
};

function show(state: GamePageState) {
	return render(GamePage, { props: { state, allGamesHref: HOME, layout: 'desktop' } });
}

afterEach(() => {
	vi.restoreAllMocks();
});

describe('GamePage', () => {
	it('shows the header skeleton and two section skeletons while loading', () => {
		const { container } = show({ kind: 'loading' });
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('header .skeleton')).not.toBeNull();
		const sections = container.querySelector('.section-skeleton');
		expect(sections?.getAttribute('aria-busy')).toBe('true');
		expect(sections?.querySelector('.bones')?.getAttribute('aria-hidden')).toBe('true');
		expect(sections?.querySelectorAll('.heading-bone')).toHaveLength(2);
		expect(sections?.querySelectorAll('.blueprint-frame')).toHaveLength(2);
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
		expect(container.querySelector('footer')).not.toBeNull();
	});

	it('shows the nav row and the data unavailable row when the feed is unavailable', () => {
		const { container } = show({ kind: 'unavailable' });
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
		expect(container.querySelector('.status-line')).toBeNull();
		expect(container.querySelector('footer')).not.toBeNull();
	});

	it('shows the nav row and "Game not found." with a link to all games for an unknown game', () => {
		show({ kind: 'not-found' });
		expect(screen.getByText('Game not found.')).toBeTruthy();
		const links = screen.getAllByRole('link', { name: 'All games' });
		expect(links).toHaveLength(2);
		for (const link of links) expect(link.getAttribute('href')).toBe('/');
	});

	it('shows the header and the tabs when ready', () => {
		const { container } = show({ kind: 'ready', view });
		expect(screen.getByText('Q3 · 4:12 · Chase Center')).toBeTruthy();
		expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(2);
		const nav = screen.getByRole('navigation', { name: 'Sections' });
		expect(nav.querySelectorAll('a')).toHaveLength(2);
		expect(container.querySelector('footer')).not.toBeNull();
	});

	it('shows a postponed game in the pre-game layout with its status tag', () => {
		const { container } = show({ kind: 'ready', view: postponed });
		expect(container.querySelector('.status-tag')?.textContent).toBe('Postponed');
		expect(container.querySelector('.tip-time')).toBeNull();
		expect(container.querySelector('.venue')).not.toBeNull();
		expect(screen.queryByRole('navigation', { name: 'Sections' })).toBeNull();
	});

	it('shows the not-found row in Spanish for an es browser', () => {
		preferLanguages(['es-ES']);
		show({ kind: 'not-found' });
		expect(screen.getByText('Partido no encontrado.')).toBeTruthy();
		expect(screen.getAllByRole('link', { name: 'Todos los partidos' }).length).toBe(2);
	});
});
