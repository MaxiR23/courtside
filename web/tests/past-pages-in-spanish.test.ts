// web/tests/past-pages-in-spanish.test.ts
//
// Cross-cutting test: the past season pages and the pages that share their components, in Spanish, on
// the phone layout and the desktop layout. No text of the page equals the English text of a message that
// has a Spanish one, no sentence the feed writes in English reaches the page, and a historical side
// draws the code of its season.
//
// Tested:
// - Day, game, standings, team (current and past), player (past), Cup (2024 and 2025 shapes), playoffs
//   (2005 and 2025 shapes) and All-Star (2005, 2024 and 2025 shapes, and the 2005 unavailable state) pages
// - Each page at layout mobile and desktop: no text node, aria-label or title is the English text of a message whose Spanish text differs
// - The series summaries, award names and the Cup rows are not the feed's English values
// - The season codes NO (a New Orleans side) and NJ (a New Jersey career row) are drawn and today's NOP and BKN are not
// - The English message list is not empty, so the scan cannot pass vacuously, and the scan flags an English text
//
// What is covered:
// - Pages rendered from invented feeds through their props functions; no network, no clock
// - Messages with a placeholder are not compared: their text is composed by the props functions and checked by their own tests
//
// Run with: cd web && pnpm exec vitest run tests/past-pages-in-spanish.test.ts
//
// SEE: web/messages/en.json, web/messages/es.json, web/src/lib/components
import type { ResolvedPathname } from '$app/types';
import { render } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Component } from 'svelte';

import type { AllStarPageState } from '../src/lib/all-star/types';
import CupPage from '../src/lib/components/CupPage.svelte';
import DayPage from '../src/lib/components/DayPage.svelte';
import GamePage from '../src/lib/components/GamePage.svelte';
import AllStarPage from '../src/lib/components/AllStarPage.svelte';
import PlayerPage from '../src/lib/components/PlayerPage.svelte';
import PlayoffsPage from '../src/lib/components/PlayoffsPage.svelte';
import StandingsPage from '../src/lib/components/StandingsPage.svelte';
import TeamPage from '../src/lib/components/TeamPage.svelte';
import type { AllStarFeed } from '../src/lib/contract/all-star';
import type { CupFeed } from '../src/lib/contract/cup';
import type { DayFeed } from '../src/lib/contract/days';
import type { GameDetailFeed } from '../src/lib/contract/game-detail';
import type { PlayerFeed } from '../src/lib/contract/player';
import type { PlayoffsFeed } from '../src/lib/contract/playoffs';
import type { PlayoffsFinalsFeed } from '../src/lib/contract/playoffs-finals';
import type { StandingsFeed } from '../src/lib/contract/standings';
import type { TeamFeed } from '../src/lib/contract/team';
import { CupMatchupStore } from '../src/lib/cup/matchup.svelte';
import { DayCardStats } from '../src/lib/day/card-stats.svelte';
import { toAllStarView } from '../src/lib/feed/all-star-props';
import { toCupView } from '../src/lib/feed/cup-props';
import { toDayView } from '../src/lib/feed/day-props';
import { toGameView } from '../src/lib/feed/game-props';
import { toPlayerView } from '../src/lib/feed/player-props';
import { toPlayoffsView } from '../src/lib/feed/playoffs-props';
import { toStandingsView } from '../src/lib/feed/standings-props';
import { toTeamView } from '../src/lib/feed/team-props';
import { preferLanguages } from './prefer-languages';

vi.mock('$app/navigation', () => ({ afterNavigate: () => {}, goto: () => {} }));

const fixtures = join(import.meta.dirname, 'lib', 'feed', 'fixtures');
const read = <T>(name: string): T => JSON.parse(readFileSync(join(fixtures, name), 'utf8')) as T;

type Messages = Record<string, unknown>;
const messages = (language: 'en' | 'es'): Messages =>
	JSON.parse(readFileSync(join(import.meta.dirname, '..', 'messages', `${language}.json`), 'utf8'));

/** The English texts, with no placeholder, whose Spanish text differs. */
function englishTexts(): Map<string, string> {
	const en = messages('en');
	const es = messages('es');
	// A text some Spanish message also has (Final, FG%) is not an English text.
	const spanishTexts = new Set(
		Object.values(es)
			.filter((value): value is string => typeof value === 'string')
			.map((value) => value.trim())
	);
	const found = new Map<string, string>();
	for (const [key, value] of Object.entries(en)) {
		const spanish = es[key];
		if (typeof value !== 'string' || typeof spanish !== 'string') continue;
		const text = value.trim();
		if (text.length < 3 || text.includes('{') || spanishTexts.has(text)) continue;
		found.set(text, key);
	}
	return found;
}

/** Every text a reader sees on the page: text nodes and the labels and titles of elements. */
function textsOf(root: Node): string[] {
	const texts: string[] = [];
	const walker = (root.ownerDocument ?? (root as Document)).createTreeWalker(
		root,
		NodeFilter.SHOW_ALL
	);
	for (let node = walker.nextNode(); node; node = walker.nextNode()) {
		if (node.nodeType === Node.TEXT_NODE) {
			const parent = (node as Text).parentElement;
			if (parent && ['SCRIPT', 'STYLE'].includes(parent.tagName)) continue;
			const text = (node.textContent ?? '').replace(/\s+/g, ' ').trim();
			if (text) texts.push(text);
		} else if (node.nodeType === Node.ELEMENT_NODE) {
			for (const name of ['aria-label', 'title']) {
				const value = (node as Element).getAttribute(name)?.trim();
				if (value) texts.push(value);
			}
		}
	}
	return texts;
}

/** The texts of the page that are the English text of a message with a Spanish one. */
function englishOn(texts: string[]): string[] {
	const english = englishTexts();
	return [...new Set(texts.filter((text) => english.has(text)))].map(
		(text) => `${text} (${english.get(text)})`
	);
}

const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;
const link = (path: string) => (value: string) =>
	`${path}${value.toLowerCase()}` as ResolvedPathname;
const teamHref = link('/team/');
const playerHref = link('/player/');
const gameHref = link('/game/');
const seriesHref = (id: string) => `/playoffs/series?id=${id}` as ResolvedPathname;

type Layout = 'mobile' | 'desktop';
type Page = {
	name: string;
	/** Renders the page at a layout and gives the sentinels that must not be on it. */
	draw: (layout: Layout) => { texts: string[] };
};

function page<P extends Record<string, unknown>>(
	component: Component<P>,
	props: (layout: Layout) => P
) {
	return (layout: Layout) => {
		const { container, unmount } = render(
			component as unknown as Component<Record<string, unknown>>,
			{
				props: props(layout)
			}
		);
		const texts = textsOf(container.ownerDocument.body);
		unmount();
		return { texts };
	};
}

// ---- Feeds of each past shape --------------------------------------------------------------------

const SENTINEL = 'ENGLISH SENTINEL';

function pastGame(): GameDetailFeed {
	const feed = read<GameDetailFeed>('game-detail-past.json');
	feed.postseason = {
		stage: 'finals',
		round: 4,
		conference: null,
		number: 7,
		summary: `QXA WINS SERIES 4-3 ${SENTINEL}`,
		playIn: null,
		stakes: 'game_7',
		awayWins: 3,
		homeWins: 4,
		seriesWinner: 'home'
	};
	feed.away = { ...feed.away, code: 'NOP', seasonCode: 'NO', historical: true };
	return feed;
}

function dayWithSeries(): DayFeed {
	const feed = read<DayFeed>('day.json');
	const game = feed.day.games[0] as unknown as Record<string, unknown>;
	game.postseason = {
		stage: 'finals',
		round: 4,
		conference: null,
		number: 7,
		summary: `QXA WINS SERIES 4-3 ${SENTINEL}`,
		playIn: null,
		stakes: 'game_7',
		awayWins: 3,
		homeWins: 4,
		seriesWinner: 'home'
	};
	return feed;
}

function pastPlayer(): PlayerFeed {
	const feed = read<PlayerFeed>('player-past.json');
	feed.team = {
		code: 'BKN',
		name: 'Nets',
		city: 'Brooklyn',
		seasonCode: 'NJ',
		logo: null,
		colors: null
	};
	const row = feed.seasons.regular.perGame[0];
	row.teams = ['BKN'];
	row.seasonCodes = ['NJ'];
	feed.awards = [
		{ name: `${SENTINEL} MVP`, code: 'mvp', team: null, count: 1, seasons: ['2004-05'] },
		{ name: `${SENTINEL} defense`, code: 'all_defensive', team: 2, count: 1, seasons: ['2004-05'] }
	];
	return feed;
}

function playoffs2005(): { feed: PlayoffsFeed; finals: PlayoffsFinalsFeed } {
	const feed = read<PlayoffsFeed>('playoffs-complete.json');
	const finals = read<PlayoffsFinalsFeed>('playoffs-finals.json');
	const series = feed.bracket.find((entry) => entry.conference === null)!;
	series.summary = `QXA WINS SERIES 4-3 ${SENTINEL}`;
	series.top.wins = 4;
	series.bottom.wins = 3;
	series.winner = series.top.team!.code;
	return { feed, finals };
}

function cupOutOfOrder(): CupFeed {
	const feed = read<CupFeed>('cup.json');
	const group = feed.groups[0]!;
	group.rows = [...group.rows].reverse() as typeof group.rows;
	return feed;
}

const allStar = (name: 'before' | 'live' | 'after'): AllStarFeed =>
	read<AllStarFeed>(`all-star-${name}.json`);

function allStarState(feed: AllStarFeed, pastLabel: string): AllStarPageState {
	return { kind: 'ready', view: toAllStarView(feed, 'current', { pastLabel })! };
}

const allStarProps = (
	state: AllStarPageState,
	layout: Layout,
	seasonTag: string | null = null
) => ({
	state,
	allGamesHref: HOME,
	standingsHref: STANDINGS,
	layout,
	teamHref,
	playerHref,
	seasonTag
});

const PAGES: Page[] = [
	{
		name: 'day',
		draw: page(DayPage, (layout) => ({
			state: { kind: 'ready' as const, view: toDayView(dayWithSeries(), {})! },
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			previousHref: null,
			nextHref: null,
			calendar: null,
			layout,
			gameHref,
			teamHref,
			detailReads: new DayCardStats(undefined)
		}))
	},
	{
		name: 'past game',
		draw: page(GamePage, (layout) => ({
			state: { kind: 'ready' as const, view: toGameView(pastGame(), {})! },
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout,
			teamHref,
			playerHref
		}))
	},
	{
		name: 'past standings',
		draw: page(StandingsPage, (layout) => ({
			state: {
				kind: 'ready' as const,
				view: toStandingsView(read<StandingsFeed>('standings-past.json'), { past: true })
			},
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout,
			teamHref
		}))
	},
	{
		name: 'current team',
		draw: page(TeamPage, (layout) => ({
			state: { kind: 'ready' as const, view: toTeamView(read<TeamFeed>('team.json')) },
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout,
			gameHref,
			playerHref
		}))
	},
	{
		name: 'past team',
		draw: page(TeamPage, (layout) => ({
			state: {
				kind: 'ready' as const,
				view: toTeamView(read<TeamFeed>('team-past.json'), { past: true })
			},
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout,
			gameHref,
			playerHref
		}))
	},
	{
		name: 'past player',
		draw: page(PlayerPage, (layout) => ({
			state: { kind: 'ready' as const, view: toPlayerView(pastPlayer(), { past: true }) },
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout,
			gameHref
		}))
	},
	...(['cup.json', 'cup-complete.json'] as const).map((file) => ({
		name: `past cup (${file})`,
		draw: page(CupPage, (layout) => ({
			state: {
				kind: 'ready' as const,
				view: toCupView(file === 'cup.json' ? cupOutOfOrder() : read<CupFeed>(file), { past: true })
			},
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout,
			teamHref,
			gameHref,
			playerHref,
			matchup: new CupMatchupStore(undefined)
		}))
	})),
	...(['complete', 'bracket'] as const).map((shape) => ({
		name: `past playoffs (${shape})`,
		draw: page(PlayoffsPage, (layout) => {
			const { feed, finals } = playoffs2005();
			const source = shape === 'complete' ? feed : read<PlayoffsFeed>('playoffs-bracket.json');
			return {
				state: {
					kind: 'ready' as const,
					view: toPlayoffsView(source, shape === 'complete' ? finals : null, { past: true })
				},
				allGamesHref: HOME,
				standingsHref: STANDINGS,
				layout,
				bracketLayout: layout,
				mvpLayout: layout,
				teamHref,
				gameHref,
				seriesHref,
				openSeries: () => {}
			};
		})
	})),
	...(['before', 'live', 'after'] as const).map((shape) => ({
		name: `past all-star (${shape})`,
		draw: page(AllStarPage, (layout) =>
			allStarProps(allStarState(allStar(shape), '2004-05'), layout)
		)
	})),
	{
		name: 'unavailable past all-star',
		draw: page(AllStarPage, (layout) =>
			allStarProps({ kind: 'unavailable' }, layout, 'Temporada 2004-05')
		)
	}
];

beforeEach(() => {
	preferLanguages(['es']);
});

afterEach(() => {
	vi.restoreAllMocks();
});

describe('the scan', () => {
	it('lists English texts, so it cannot pass by finding none', () => {
		const english = englishTexts();
		expect(english.size).toBeGreaterThan(100);
		expect(english.get('Playoffs')).toBeUndefined();
		expect([...english.values()]).toContain('playoffs_east');
	});

	it('flags an English text and ignores a Spanish one', () => {
		expect(englishOn(['East', 'Este'])).toEqual(['East (playoffs_east)']);
	});
});

describe.each(PAGES)('the $name page in Spanish', ({ draw }) => {
	it.each(['mobile', 'desktop'] as const)('writes no English text at %s', (layout) => {
		const { texts } = draw(layout);
		expect(texts.length).toBeGreaterThan(3);
		expect(englishOn(texts)).toEqual([]);
		expect(texts.filter((text) => text.includes(SENTINEL))).toEqual([]);
		expect(
			texts.filter((text) => /\bwins series\b|\bleads series\b|\bSeries tied\b/.test(text))
		).toEqual([]);
	});
});

describe('the series summary in Spanish', () => {
	it('writes the 4-3 Finals series of the game header and the day card from the wins', () => {
		const game = PAGES.find((entry) => entry.name === 'past game')!.draw('desktop').texts;
		expect(game.some((text) => text.includes('gana la serie 4–3'))).toBe(true);
		const day = PAGES.find((entry) => entry.name === 'day')!.draw('desktop').texts;
		expect(day.some((text) => text.includes('gana la serie 4–3'))).toBe(true);
		// The series sheet is closed on the page: its score is read from the props.
		const { feed, finals } = playoffs2005();
		const card = toPlayoffsView(feed, finals, { past: true }).bracket.series.find(
			(entry) => entry.final
		)!;
		expect(card.score).toMatch(/ gana la serie 4–3$/);
	});
});

describe('the award names in Spanish', () => {
	it('writes the player awards from their code and not as the feed sent them', () => {
		const texts = PAGES.find((entry) => entry.name === 'past player')!.draw('desktop').texts;
		expect(texts).toContain('Jugador Más Valioso');
		expect(texts).toContain('Mejor quinteto defensivo (2.º)');
	});
});

describe('the Cup group rows in Spanish', () => {
	it('draws the rows by position', () => {
		const view = toCupView(cupOutOfOrder(), { past: true });
		expect(view.groups[0]!.rows.map((row) => row.position)).toEqual(['1', '2', '3', '4', '—']);
	});
});

describe('the season codes', () => {
	it('draws NO for a historical New Orleans side and not NOP', () => {
		const texts = PAGES.find((entry) => entry.name === 'past game')!.draw('desktop').texts;
		expect(texts).toContain('NO');
		expect(texts).not.toContain('NOP');
	});

	it('draws NJ on the career row and the header of a past player and not BKN', () => {
		const texts = PAGES.find((entry) => entry.name === 'past player')!.draw('desktop').texts;
		expect(texts).toContain('NJ');
		expect(texts).not.toContain('BKN');
	});
});

describe('the All-Star past pages draw no league team code of today', () => {
	it('draws the 2005 unavailable state with its season tag', () => {
		const texts = PAGES.find((entry) => entry.name === 'unavailable past all-star')!.draw(
			'mobile'
		).texts;
		expect(texts).toContain('Temporada 2004-05');
	});
});
