// web/tests/lib/components/GamePage.test.ts
//
// Tests for the GamePage component.
//
// Tested:
// - Loading: the header skeleton and two section skeletons, busy and hidden from assistive tech
// - Feed unavailable: the nav row and the data unavailable row
// - Unknown game: the nav row and "Game not found." with a link to all games
// - Ready: the header and the tabs; a postponed game in the pre-game layout with its status tag
// - Ready: each section in the design order with its tab id as anchor, none when null
// - The section metas: the platform for highlights, the leader for win probability, the injury report, the series count, the new tab
// - No link inside a button or another link, and the header team names link to the team page
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
import type { BoxRow, GamePageState, GameSections, GameView } from '../../../src/lib/game/types';
import { preferLanguages } from '../../prefer-languages';

const HOME = '/' as ResolvedPathname;
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;

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
	miniScore: { awayCode: 'LAL', away: 63, home: 62, homeCode: 'GSW' },
	sections: {
		highlights: null,
		players: null,
		score: null,
		winProbability: null,
		boxScore: null,
		injuries: null,
		lastGames: null,
		standings: null,
		seasonSeries: null,
		videos: null
	}
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
	miniScore: null,
	sections: {
		highlights: null,
		players: null,
		score: null,
		winProbability: null,
		boxScore: null,
		injuries: null,
		lastGames: null,
		standings: null,
		seasonSeries: null,
		videos: null
	}
};

const row: BoxRow = {
	id: 'p1',
	name: 'LeBron James',
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
	plusMinus: '+4',
	plusMinusPositive: true
};
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
const stat = { fieldGoalPct: 0.5, threePointPct: 0.35, rebounds: 30, assists: 18, turnovers: 9 };
const detailStat = { ...stat, freeThrowPct: 0.8, steals: 5, blocks: 3 };
const awayStar = {
	id: 'p-away',
	firstName: 'Stephen',
	lastName: 'Curry',
	teamCode: 'LAL',
	photo: '/a.svg'
};
const homeStar = {
	id: 'p-home',
	firstName: 'Anthony',
	lastName: 'Davis',
	teamCode: 'GSW',
	photo: '/h.svg'
};
const lastTeam = (code: string, name: string) => ({
	code,
	name,
	strip: [{ result: 'win' as const, label: 'W' }],
	rows: [
		{
			result: 'win' as const,
			resultLabel: 'W',
			date: 'Oct 5',
			opponent: 'vs DEN',
			score: '118–104'
		}
	]
});
const standing = (code: string, name: string) => ({
	code,
	name,
	conference: '3rd West',
	record: '12–5',
	home: '7–2',
	away: '5–3',
	lastTen: '7–3'
});
const full: GameSections = {
	players: {
		away: { ...awayStar, teamName: 'Los Angeles Lakers' },
		home: { ...homeStar, teamName: 'Golden State Warriors' }
	},
	injuries: {
		away: {
			code: 'LAL',
			name: 'Lakers',
			injuries: [{ id: 'p9', name: 'A B', status: 'out', comment: null }]
		},
		home: { code: 'GSW', name: 'Warriors', injuries: [] }
	},
	lastGames: { away: lastTeam('LAL', 'Lakers'), home: lastTeam('GSW', 'Warriors') },
	standings: { away: standing('LAL', 'Lakers'), home: standing('GSW', 'Warriors') },
	seasonSeries: {
		summary: 'LAL lead 1–0',
		meta: '1 of 3 games played',
		games: [
			{
				date: 'Jan 10',
				current: false,
				awayCode: 'LAL',
				awayPoints: 110,
				homePoints: 100,
				homeCode: 'GSW',
				loser: 'home',
				arena: 'Arena'
			}
		]
	},
	videos: [{ title: 'Recap', duration: '2:14', thumbnail: null, href: '/video' }],
	highlights: {
		platform: 'Video platform',
		searchUrl: '/search',
		videos: [{ id: 'v1', title: 'Clip', channel: 'Channel', thumbnail: '/t.svg', embedUrl: '/e/1' }]
	},
	score: {
		lineScore: {
			away: { code: 'LAL', name: 'Lakers', periods: [28, 25, 10], total: 63 },
			home: { code: 'GSW', name: 'Warriors', periods: [26, 24, 12], total: 62 }
		},
		stats: {
			away: detailStat,
			home: detailStat,
			leads: {
				fieldGoalPct: null,
				threePointPct: null,
				freeThrowPct: null,
				rebounds: null,
				assists: null,
				turnovers: null,
				steals: null,
				blocks: null
			}
		}
	},
	winProbability: {
		awayCode: 'LAL',
		homeCode: 'GSW',
		middle: '50%',
		meta: 'GSW 68%',
		points: [
			{ elapsedSeconds: 0, homeWinProbability: 0.5 },
			{ elapsedSeconds: 60, homeWinProbability: 0.68 }
		],
		boundaries: null
	},
	boxScore: {
		away: { code: 'LAL', name: 'Lakers', starters: [row], bench: [], totals },
		home: { code: 'GSW', name: 'Warriors', starters: [row], bench: [], totals }
	}
};
const withSections = (sections: GameSections): GameView => ({ ...view, sections });

function show(state: GamePageState) {
	return render(GamePage, {
		props: { state, allGamesHref: HOME, layout: 'desktop', teamHref, playerHref }
	});
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

	it('renders each section with its tab id as anchor, in the design order', () => {
		const { container } = show({ kind: 'ready', view: withSections(full) });
		const sections = [...container.querySelectorAll('.sections > section')];
		expect(sections.map((s) => s.id)).toEqual([
			'highlights',
			'players',
			'score',
			'win-probability',
			'box-score',
			'injuries',
			'last-games',
			'standings',
			'season-series',
			'videos'
		]);
		expect(sections.map((s) => s.querySelector('h2')?.textContent)).toEqual([
			'Highlights',
			'Players to watch',
			'Score',
			'Win probability',
			'Box score',
			'Injuries',
			'Last 5 games',
			'Standings',
			'Season series',
			'Videos'
		]);
	});

	it('renders no section whose data is null', () => {
		const { container } = show({
			kind: 'ready',
			view: withSections({
				...full,
				highlights: null,
				boxScore: null,
				players: null,
				injuries: null,
				lastGames: null,
				standings: null,
				seasonSeries: null,
				videos: null
			})
		});
		expect([...container.querySelectorAll('.sections > section')].map((s) => s.id)).toEqual([
			'score',
			'win-probability'
		]);
		const empty = show({ kind: 'ready', view });
		expect(empty.container.querySelector('.sections > section')).toBeNull();
	});

	it('shows the platform as the highlights section meta and the leader as the win probability meta', () => {
		const { container } = show({ kind: 'ready', view: withSections(full) });
		expect(container.querySelector('#highlights .meta')?.textContent).toBe('Video platform');
		expect(container.querySelector('#win-probability .meta')?.textContent).toBe('GSW 68%');
		expect(container.querySelector('#score .meta')).toBeNull();
	});

	it('shows the injury report, the series count and the new tab note as section metas', () => {
		const { container } = show({ kind: 'ready', view: withSections(full) });
		expect(container.querySelector('#injuries .meta')?.textContent).toBe('Injury report');
		expect(container.querySelector('#season-series .meta')?.textContent).toBe(
			'1 of 3 games played'
		);
		expect(container.querySelector('#videos .meta')?.textContent).toBe('Opens in a new tab');
		expect(container.querySelector('#players .meta')).toBeNull();
		expect(container.querySelector('#standings .meta')).toBeNull();
	});

	it('shows a postponed game in the pre-game layout with its status tag', () => {
		const { container } = show({ kind: 'ready', view: postponed });
		expect(container.querySelector('.status-tag')?.textContent).toBe('Postponed');
		expect(container.querySelector('.tip-time')).toBeNull();
		expect(container.querySelector('.venue')).not.toBeNull();
		expect(screen.queryByRole('navigation', { name: 'Sections' })).toBeNull();
	});

	it('renders no link inside a button or another link', () => {
		const { container } = show({ kind: 'ready', view: withSections(full) });
		expect(container.querySelectorAll('a').length).toBeGreaterThan(0);
		expect(container.querySelectorAll('button a, a a')).toHaveLength(0);
	});

	it('links the header team names to the team page', () => {
		const { container } = show({ kind: 'ready', view });
		const names = [...container.querySelectorAll('h1 a')];
		expect(names.map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
			['Lakers', '/team/lal'],
			['Warriors', '/team/gsw']
		]);
	});

	it('shows the not-found row in Spanish for an es browser', () => {
		preferLanguages(['es-ES']);
		show({ kind: 'not-found' });
		expect(screen.getByText('Partido no encontrado.')).toBeTruthy();
		expect(screen.getAllByRole('link', { name: 'Todos los partidos' }).length).toBe(2);
	});
});
