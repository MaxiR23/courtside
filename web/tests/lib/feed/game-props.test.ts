// web/tests/lib/feed/game-props.test.ts
//
// Tests for the props layer that turns the game detail feed into the game page props.
//
// Tested:
// - A live game: live layout, "Q3 · 4:12 · {arena}", the score, the mini score
// - Period and clock pass through as the feed sends them, including 0:00; OT1 and OT2
// - A final game: "Final · {date} · {arena}", the loser from the feed winner
// - A scheduled game: pre-game layout, tip time, broadcast and venue strip; delayed, postponed
//   and canceled variants
// - The record as wins–losses; no broadcast cell when the network is unknown
// - The tabs: the design order per layout, hidden when their data is null, highlights only with
//   a platform name and a search URL
// - The sections: built from the feed, null with their tab, leaders from the feed, the win
//   probability meta, box score split and formatting, highlights on a final game
// - The pre-game sections: players by side, injuries, last games (strip order, row format), standings,
//   the season series summary (leader from the feed) and meta, the "This game" row and the dimmed
//   loser, videos; null with their tab; the date shown in UTC
//   (the current series row comes from the feed marker, not from the date or the position)
// - Spanish copy and dates for an es browser
// - A live game without its score cannot be shown
//
// What is covered:
// - Pure logic on a recorded feed (tests/lib/feed/fixtures/game-detail.json); no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/game-props.test.ts
//
// SEE: web/src/lib/feed/game-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GameDetailFeed } from '../../../src/lib/contract/game-detail';
import { SECTION_TABS, toGameView } from '../../../src/lib/feed/game-props';
import type { GameView } from '../../../src/lib/game/types';
import { preferLanguages } from '../../prefer-languages';

const feed = (): GameDetailFeed =>
	JSON.parse(
		readFileSync(join(__dirname, 'fixtures', 'game-detail.json'), 'utf8')
	) as GameDetailFeed;
const options: { videoPlatformName?: string } = { videoPlatformName: 'Video platform' };

type Periods = NonNullable<GameDetailFeed['winProbabilityPeriods']>['periods'];

function view(source: GameDetailFeed, opts = options): GameView {
	const result = toGameView(source, opts);
	if (!result) throw new Error('The fixture feed must be showable');
	return result;
}

function asFinal(source: GameDetailFeed): GameDetailFeed {
	return { ...source, status: 'final', period: null, clock: null, winner: 'LAL' };
}

function asStatus(status: GameDetailFeed['status']): GameDetailFeed {
	return {
		...feed(),
		status,
		period: null,
		clock: null,
		lineScore: null,
		score: null,
		teamStats: null,
		boxScore: null,
		winProbability: null
	};
}

const ids = (v: GameView) => v.tabs.map((tab) => tab.id);

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toGameView', () => {
	it('maps a live game to the live layout with "Q3 · 4:12 · {arena}" and the score', () => {
		const v = view(feed());
		expect(v.header.layout).toBe('live');
		expect(v.header.status).toEqual({ state: 'live', text: 'Q3 · 4:12 · Chase Center' });
		expect(v.header.center).toEqual({ kind: 'score', away: 63, home: 62, loser: null });
		expect(v.header.venue).toBeNull();
	});

	it('shows period and clock as the feed sends them, including 0:00', () => {
		expect(view({ ...feed(), period: 2, clock: '0:00' }).header.status.text).toBe(
			'Q2 · 0:00 · Chase Center'
		);
		expect(view({ ...feed(), period: 1, clock: '0:00' }).header.status.text).toBe(
			'Q1 · 0:00 · Chase Center'
		);
	});

	it('labels overtime periods OT1 and OT2', () => {
		expect(view({ ...feed(), period: 5, clock: '2:30' }).header.status.text).toBe(
			'OT1 · 2:30 · Chase Center'
		);
		expect(view({ ...feed(), period: 6, clock: '2:30' }).header.status.text).toBe(
			'OT2 · 2:30 · Chase Center'
		);
	});

	it('maps a final game to "Final · {date} · {arena}" with the loser from the feed winner', () => {
		const v = view(asFinal(feed()));
		expect(v.header.layout).toBe('final');
		expect(v.header.status).toEqual({
			state: 'final',
			text: 'Final · Wednesday, October 7 · Chase Center'
		});
		expect(v.header.center).toEqual({ kind: 'score', away: 63, home: 62, loser: 'home' });
		expect(view({ ...asFinal(feed()), winner: 'GSW' }).header.center).toMatchObject({
			loser: 'away'
		});
	});

	it('maps a scheduled game to the pre-game layout with the tip time, broadcast and venue strip', () => {
		const v = view(asStatus('scheduled'));
		expect(v.header.layout).toBe('pre-game');
		expect(v.header.status).toEqual({
			state: 'scheduled',
			text: 'Wednesday, October 7 · Chase Center'
		});
		expect(v.header.center).toEqual({
			kind: 'tip-off',
			tipTime: '7:00',
			tipSuffix: 'PM ET',
			broadcast: 'Network One',
			delayed: false
		});
		expect(v.header.venue).toEqual({
			arena: 'Chase Center',
			city: 'San Francisco',
			photo: 'https://example.com/venues/chase.jpg',
			cells: [
				{ label: 'Tip-off', value: '7:00 PM ET', sub: 'Wednesday, October 7' },
				{ label: 'Venue', value: 'Chase Center', sub: 'San Francisco' },
				{ label: 'Broadcast', value: 'Network One', sub: null }
			]
		});
		expect(v.miniScore).toBeNull();
	});

	it('marks a delayed game as scheduled before its original time', () => {
		const v = view(asStatus('delayed'));
		expect(v.header.status.state).toBe('delayed');
		expect(v.header.center).toMatchObject({ kind: 'tip-off', tipTime: '7:00', delayed: true });
	});

	it('shows no time for postponed and canceled games and keeps their venue strip without a tip-off cell', () => {
		for (const status of ['postponed', 'canceled'] as const) {
			const v = view(asStatus(status));
			expect(v.header.layout).toBe('pre-game');
			expect(v.header.status.state).toBe(status);
			expect(v.header.center).toEqual({ kind: 'none' });
			expect(v.header.venue?.cells.map((cell) => cell.label)).toEqual(['Venue', 'Broadcast']);
		}
	});

	it('formats the record as wins–losses', () => {
		const v = view(feed());
		expect(v.header.away).toEqual({
			code: 'LAL',
			name: 'Lakers',
			city: 'Los Angeles',
			record: '12–5'
		});
		expect(v.header.home.record).toBe('10–7');
	});

	it('keeps the design order of tabs per layout', () => {
		expect(ids(view(asStatus('scheduled')))).toEqual(SECTION_TABS['pre-game']);
		expect(ids(view(feed()))).toEqual(['score', 'win-probability', 'box-score', 'injuries']);
		expect(ids(view(asFinal(feed())))).toEqual(SECTION_TABS.final);
		const labels = view(asFinal(feed())).tabs.map((tab) => tab.label);
		expect(labels).toEqual([
			'Highlights',
			'Score',
			'Win prob.',
			'Box score',
			'Injuries',
			'Series',
			'Videos'
		]);
		expect(view(asStatus('scheduled')).tabs.map((tab) => tab.label)).toEqual([
			'Players',
			'Injuries',
			'Last 5',
			'Standings',
			'Season series'
		]);
	});

	it('hides the tab of every section whose data is null', () => {
		const source = {
			...asFinal(feed()),
			lineScore: null,
			winProbability: null,
			boxScore: null,
			injuries: null,
			seasonSeries: null,
			videos: null
		} as unknown as GameDetailFeed;
		expect(ids(view(source))).toEqual(['highlights']);
		const pre = {
			...asStatus('scheduled'),
			stars: null,
			lastGames: null,
			standings: null
		} as unknown as GameDetailFeed;
		expect(ids(view(pre))).toEqual(['injuries', 'season-series']);
	});

	it('hides the highlights tab without a video platform name or a search URL', () => {
		expect(ids(view(asFinal(feed()), {}))).not.toContain('highlights');
		const noSearch = { ...asFinal(feed()), highlightsSearchUrl: null };
		expect(ids(view(noSearch))).not.toContain('highlights');
		expect(ids(view({ ...asFinal(feed()), highlights: [] }))).toContain('highlights');
	});

	it('shows the mini score on live and final games only', () => {
		const expected = { awayCode: 'LAL', away: 63, home: 62, homeCode: 'GSW' };
		expect(view(feed()).miniScore).toEqual(expected);
		expect(view(asFinal(feed())).miniScore).toEqual(expected);
		expect(view(asStatus('scheduled')).miniScore).toBeNull();
		expect(view(asStatus('postponed')).miniScore).toBeNull();
	});

	it('omits the broadcast cell when the broadcast is unknown', () => {
		const v = view({ ...asStatus('scheduled'), broadcast: null });
		expect(v.header.venue?.cells.map((cell) => cell.label)).toEqual(['Tip-off', 'Venue']);
		expect(v.header.center).toMatchObject({ broadcast: null });
	});

	it('formats the date and labels in Spanish for an es browser', () => {
		preferLanguages(['es-ES']);
		const v = view(asFinal(feed()));
		expect(v.header.status.text).toMatch(/^Final · miércoles, 7 de octubre · Chase Center$/);
		expect(v.tabs[0].label).toBe('Resúmenes');
		expect(view({ ...feed(), period: 2, clock: '0:00' }).header.status.text).toBe(
			'C2 · 0:00 · Chase Center'
		);
	});

	it('returns null when a live game lacks its score', () => {
		expect(toGameView({ ...feed(), score: null } as unknown as GameDetailFeed, options)).toBeNull();
		expect(toGameView({ ...feed(), clock: null } as unknown as GameDetailFeed, options)).toBeNull();
	});
});

describe('toGameView sections', () => {
	it('builds every live section from the feed, with no highlights on a live game', () => {
		const { sections } = view(feed());
		expect(sections.highlights).toBeNull();
		expect(sections.score?.lineScore.away).toEqual({
			code: 'LAL',
			name: 'Lakers',
			periods: [28, 25, 10],
			total: 63
		});
		expect(sections.score?.lineScore.home.total).toBe(62);
		expect(sections.score?.stats?.away.freeThrowPct).toBe(0.8);
		expect(sections.winProbability?.awayCode).toBe('LAL');
		expect(sections.winProbability?.homeCode).toBe('GSW');
		expect(sections.winProbability?.middle).toBe('50%');
		expect(sections.boxScore?.away.code).toBe('LAL');
		expect(sections.boxScore?.home.name).toBe('Warriors');
	});

	it('gives each section a null when its tab is hidden', () => {
		const hidden = view({
			...feed(),
			lineScore: null,
			winProbability: null,
			boxScore: null
		});
		expect(ids(hidden)).not.toContain('score');
		expect(hidden.sections).toMatchObject({
			highlights: null,
			players: null,
			score: null,
			winProbability: null,
			boxScore: null,
			lastGames: null,
			standings: null,
			seasonSeries: null,
			videos: null
		});
		const noPlatform = view(asFinal(feed()), {});
		expect(noPlatform.sections.highlights).toBeNull();
		expect(ids(noPlatform)).not.toContain('highlights');
	});

	it("takes each team stat's leading side from the feed leaders", () => {
		const leads = view(feed()).sections.score?.stats?.leads;
		expect(leads).toEqual({
			fieldGoalPct: 'away',
			threePointPct: 'home',
			freeThrowPct: null,
			rebounds: 'away',
			assists: 'home',
			turnovers: null,
			steals: 'home',
			blocks: 'away'
		});
	});

	it('leaves the stats out of the score section when the feed has no team stats', () => {
		const { sections } = view({ ...feed(), teamStats: null });
		expect(sections.score).not.toBeNull();
		expect(sections.score?.stats).toBeNull();
	});

	it('reads the win probability meta off the latest point: the leader and its percentage', () => {
		const withLatest = (p: number) =>
			view({
				...feed(),
				winProbability: [
					{ elapsedSeconds: 0, homeWinProbability: 0.5 },
					{ elapsedSeconds: 60, homeWinProbability: p }
				]
			}).sections.winProbability?.meta;
		expect(withLatest(0.68)).toBe('GSW 68%');
		expect(withLatest(0.25)).toBe('LAL 75%');
		expect(withLatest(0.5)).toBe('50%');
	});

	it("reads '{team} win' as the win probability meta on a final game", () => {
		expect(view(asFinal(feed())).sections.winProbability?.meta).toBe('LAL win');
	});

	it('copies the win probability points in feed order without counting periods', () => {
		const points = [
			{ elapsedSeconds: 3000, homeWinProbability: 0.6 },
			{ elapsedSeconds: 100, homeWinProbability: 0.4 }
		] as GameDetailFeed['winProbability'];
		const result = view({ ...feed(), winProbability: points }).sections.winProbability;
		expect(result?.points).toEqual(points);
		expect(Object.keys(result ?? {})).not.toContain('overtimes');
	});

	it('labels each period of the feed Q1 to Q4 and OT1, OT2, with its start and the game end', () => {
		const starts = [0, 720, 1440, 2160, 2880, 3180];
		const source: GameDetailFeed = {
			...feed(),
			winProbabilityPeriods: {
				periods: starts.map((startElapsedSeconds, i) => ({
					number: i + 1,
					startElapsedSeconds
				})) as Periods,
				endElapsedSeconds: 3480
			}
		};
		expect(view(source).sections.winProbability?.boundaries).toEqual({
			periods: [
				{ label: 'Q1', start: 0 },
				{ label: 'Q2', start: 720 },
				{ label: 'Q3', start: 1440 },
				{ label: 'Q4', start: 2160 },
				{ label: 'OT1', start: 2880 },
				{ label: 'OT2', start: 3180 }
			],
			end: 3480
		});
	});

	it('gives null boundaries when the feed has no period boundaries', () => {
		const source: GameDetailFeed = { ...feed(), winProbabilityPeriods: null };
		expect(view(source).sections.winProbability?.boundaries).toBeNull();
	});

	it('labels the periods in Spanish for an es browser', () => {
		preferLanguages(['es-ES']);
		const source: GameDetailFeed = {
			...feed(),
			winProbabilityPeriods: {
				periods: [0, 720, 1440, 2160, 2880].map((startElapsedSeconds, i) => ({
					number: i + 1,
					startElapsedSeconds
				})) as Periods,
				endElapsedSeconds: 3180
			}
		};
		const labels = view(source).sections.winProbability?.boundaries?.periods.map((p) => p.label);
		expect(labels).toEqual(['C1', 'C2', 'C3', 'C4', 'PR1']);
	});

	it('splits the box score into starters and bench in feed order and formats shooting as made-attempted', () => {
		const source = feed();
		const [first] = source.boxScore?.away.players ?? [];
		if (!source.boxScore) throw new Error('The fixture has a box score');
		source.boxScore.away.players = [
			{ ...first, playerId: 'b1', displayName: 'Bench One', starter: false },
			{ ...first, playerId: 's1', displayName: 'Starter One', starter: true },
			{ ...first, playerId: 'b2', displayName: 'Bench Two', starter: false }
		];
		const away = view(source).sections.boxScore?.away;
		expect(away?.starters.map((r) => r.name)).toEqual(['Starter One']);
		expect(away?.bench.map((r) => r.name)).toEqual(['Bench One', 'Bench Two']);
		expect(away?.starters[0]).toMatchObject({
			id: 's1',
			minutes: '24:10',
			points: '20',
			fieldGoals: '8-15',
			threePoints: '2-6',
			freeThrows: '2-2'
		});
		expect(away?.totals.fieldGoalPct).toMatch(/^\d+\.\d%$/);
	});

	it('formats the plus-minus with its sign', () => {
		const source = feed();
		const [first] = source.boxScore?.away.players ?? [];
		if (!source.boxScore) throw new Error('The fixture has a box score');
		source.boxScore.away.players = [4, 0, -3].map((plusMinus, i) => ({
			...first,
			playerId: `p${i}`,
			starter: true,
			plusMinus
		}));
		const rows = view(source).sections.boxScore?.away.starters ?? [];
		expect(rows.map((r) => r.plusMinus)).toEqual(['+4', '0', '-3']);
		expect(rows.map((r) => r.plusMinusPositive)).toEqual([true, false, false]);
	});

	it("maps highlights with the home's autoplay embed URLs on a final game", () => {
		const highlights = view(asFinal(feed())).sections.highlights;
		expect(highlights?.platform).toBe('Video platform');
		expect(highlights?.searchUrl).toBe('https://example.com/search?q=lakers+warriors');
		expect(highlights?.videos).toHaveLength(1);
		expect(highlights?.videos[0]).toMatchObject({
			id: 'https://example.com/embed/1',
			title: 'Curry hits a deep three',
			channel: 'Channel One',
			thumbnail: 'https://example.com/thumbs/1.jpg'
		});
		expect(highlights?.videos[0].embedUrl).toContain('autoplay=1');
	});
});

describe('toGameView pre-game sections', () => {
	const pre = () => asStatus('scheduled');

	it('builds the players section from each side with the full team name', () => {
		const { players } = view(pre()).sections;
		expect(players?.away).toEqual({
			firstName: 'LeBron',
			lastName: 'James',
			teamCode: 'LAL',
			photo: 'https://example.com/photos/LAL.png',
			teamName: 'Los Angeles Lakers'
		});
		expect(players?.home.teamName).toBe('Golden State Warriors');
		expect(players?.home.lastName).toBe('Curry');
	});

	it('builds the injuries section with the status key and the comment as given', () => {
		const source = pre();
		source.injuries = {
			away: [
				{ displayName: 'Austin Reaves', status: 'questionable', comment: 'Hamstring.' },
				{ displayName: 'Rui Hachimura', status: 'out', comment: null }
			],
			home: []
		};
		const { injuries } = view(source).sections;
		expect(injuries?.away).toEqual({
			code: 'LAL',
			name: 'Lakers',
			injuries: [
				{ name: 'Austin Reaves', status: 'questionable', comment: 'Hamstring.' },
				{ name: 'Rui Hachimura', status: 'out', comment: null }
			]
		});
		expect(injuries?.home.injuries).toEqual([]);
	});

	it('lists last games newest first with the result strip oldest to newest', () => {
		const { lastGames } = view(pre()).sections;
		expect(lastGames?.away.rows.map((r) => r.date)).toEqual(['Oct 5', 'Oct 3']);
		expect(lastGames?.away.strip).toEqual([
			{ result: 'loss', label: 'L' },
			{ result: 'win', label: 'W' }
		]);
		expect(lastGames?.home.strip).toEqual([{ result: 'win', label: 'W' }]);
	});

	it('formats a last game as W, "Oct 5", "vs DEN" at home and "@ PHX" away, with the team points first', () => {
		const { lastGames } = view(pre()).sections;
		expect(lastGames?.away.rows[0]).toEqual({
			result: 'win',
			resultLabel: 'W',
			date: 'Oct 5',
			opponent: 'vs DEN',
			score: '110–102'
		});
		expect(lastGames?.away.rows[1]).toMatchObject({ opponent: '@ PHX', score: '99–104' });
		expect(lastGames?.home.rows[0].opponent).toBe('@ SAC');
	});

	it('shows the last-games tab and section when the feed has lastGames with at least one game', () => {
		const source = pre();
		source.lastGames = { away: source.lastGames?.away ?? [], home: [] };
		const v = view(source);
		expect(ids(v)).toContain('last-games');
		expect(v.sections.lastGames).not.toBeNull();
	});

	it('hides the last-games tab and section when both teams have no games', () => {
		const source = pre();
		source.lastGames = { away: [], home: [] };
		const v = view(source);
		expect(ids(v)).not.toContain('last-games');
		expect(v.sections.lastGames).toBeNull();
	});

	it('hides the last-games tab and section when lastGames is null', () => {
		const source = pre();
		source.lastGames = null;
		const v = view(source);
		expect(ids(v)).not.toContain('last-games');
		expect(v.sections.lastGames).toBeNull();
	});

	it('formats a contract date such as 2026-01-01 as "Jan 1", in UTC', () => {
		const source = pre();
		source.lastGames = {
			away: [
				{
					date: '2026-01-01',
					opponent: 'DEN',
					isHome: true,
					result: 'win',
					teamScore: 100,
					opponentScore: 90
				}
			],
			home: []
		};
		const spy = vi.spyOn(Intl, 'DateTimeFormat');
		expect(view(source).sections.lastGames?.away.rows[0].date).toBe('Jan 1');
		const zones = spy.mock.calls.map((call) => (call[1] as Intl.DateTimeFormatOptions).timeZone);
		expect(zones).toContain('UTC');
	});

	it('formats the conference rank as 3rd West, and 1st, 2nd and 11th', () => {
		const source = pre();
		const standings = source.standings!;
		const rank = (n: number, conference: 'east' | 'west') => {
			standings.away = { ...standings.away, conferenceRank: n, conference };
			return view(source).sections.standings?.away.conference;
		};
		expect(rank(3, 'west')).toBe('3rd West');
		expect(rank(1, 'east')).toBe('1st East');
		expect(rank(2, 'west')).toBe('2nd West');
		expect(rank(11, 'west')).toBe('11th West');
	});

	it('formats the conference rank in Spanish', () => {
		preferLanguages(['es-ES']);
		expect(view(pre()).sections.standings?.away.conference).toBe('3.º Oeste');
	});

	it('formats the standings records as wins–losses', () => {
		const { standings } = view(pre()).sections;
		expect(standings?.away).toMatchObject({
			code: 'LAL',
			name: 'Lakers',
			record: '12–5',
			home: '8–2',
			away: '4–3',
			lastTen: '6–4'
		});
		expect(standings?.home.record).toBe('10–7');
	});

	it('summarises the series as "LAL lead 1–0", "GSW lead 2–1", "Series tied 1–1" and "First meeting"', () => {
		expect(view(pre()).sections.seasonSeries?.summary).toBe('LAL lead 1–0');
		const homeLeads = pre();
		homeLeads.seasonSeries = {
			...homeLeads.seasonSeries!,
			awayWins: 1,
			homeWins: 2,
			leader: 'GSW'
		};
		expect(view(homeLeads).sections.seasonSeries?.summary).toBe('GSW lead 2–1');
		const tied = pre();
		const [played, tonight] = tied.seasonSeries!.games;
		tied.seasonSeries = {
			...tied.seasonSeries!,
			awayWins: 1,
			homeWins: 1,
			leader: null,
			games: [played, { ...played, winner: 'GSW' }, tonight]
		};
		expect(view(tied).sections.seasonSeries?.summary).toBe('Series tied 1–1');
		const first = pre();
		first.seasonSeries = {
			totalGames: 3,
			awayWins: 0,
			homeWins: 0,
			leader: null,
			games: [first.seasonSeries!.games[1]]
		};
		expect(view(first).sections.seasonSeries?.summary).toBe('First meeting');
		first.seasonSeries = { ...first.seasonSeries, games: [] };
		const section = view(first).sections.seasonSeries;
		expect(section?.summary).toBe('First meeting');
		expect(section?.games).toEqual([]);
	});

	it('takes the series leader from the feed, not from the win counts', () => {
		const source = pre();
		source.seasonSeries = {
			...source.seasonSeries!,
			awayWins: 2,
			homeWins: 1,
			leader: 'GSW'
		};
		expect(view(source).sections.seasonSeries?.summary).toBe('GSW lead 1–2');
	});

	it('shows "1 of 3 games played" as the series meta, counting completed games only', () => {
		expect(view(pre()).sections.seasonSeries?.meta).toBe('1 of 3 games played');
	});

	it('marks the current game "This game" and dims the loser from the feed winner', () => {
		const { seasonSeries } = view(pre()).sections;
		expect(seasonSeries?.games).toEqual([
			{
				date: 'Jan 10',
				current: false,
				awayCode: 'LAL',
				awayPoints: 118,
				homePoints: 112,
				homeCode: 'GSW',
				loser: 'home',
				arena: 'Chase Center'
			},
			{
				date: 'This game',
				current: true,
				awayCode: 'LAL',
				awayPoints: null,
				homePoints: null,
				homeCode: 'GSW',
				loser: null,
				arena: 'Chase Center'
			}
		]);
	});

	it('shows the points and loser of a completed current game and keeps "This game"', () => {
		const source = pre();
		const [played, tonight] = source.seasonSeries!.games;
		source.seasonSeries = {
			...source.seasonSeries!,
			games: [played, { ...tonight, score: { away: 100, home: 105 }, winner: 'GSW' }]
		};
		expect(view(source).sections.seasonSeries?.games[1]).toMatchObject({
			date: 'This game',
			current: true,
			awayPoints: 100,
			homePoints: 105,
			loser: 'away'
		});
	});

	it('labels the row the feed marks as current, whatever its date', () => {
		const source = pre();
		const [played, current] = source.seasonSeries!.games;
		source.seasonSeries = {
			...source.seasonSeries!,
			games: [
				{ ...played, isCurrent: true },
				{ ...current, isCurrent: false }
			]
		};
		const games = view(source).sections.seasonSeries!.games;
		expect(games.map((g) => g.date)).toEqual(['This game', 'Oct 7']);
		expect(games.map((g) => g.current)).toEqual([true, false]);
	});

	it('passes videos through with a null thumbnail kept null', () => {
		const { videos } = view(asFinal(feed())).sections;
		expect(videos).toEqual([
			{
				title: 'Game recap',
				duration: '2:10',
				thumbnail: null,
				href: 'https://example.com/videos/1'
			}
		]);
	});

	it('leaves each new section null when its feed field is null', () => {
		const source = {
			...asFinal(feed()),
			injuries: null,
			seasonSeries: null,
			videos: null
		} as unknown as GameDetailFeed;
		const { sections } = view(source);
		expect(sections.injuries).toBeNull();
		expect(sections.seasonSeries).toBeNull();
		expect(sections.videos).toBeNull();
		const bare = {
			...pre(),
			stars: null,
			lastGames: null,
			standings: null
		} as unknown as GameDetailFeed;
		const { sections: preSections } = view(bare);
		expect(preSections.players).toBeNull();
		expect(preSections.lastGames).toBeNull();
		expect(preSections.standings).toBeNull();
	});

	it('shows the new section copy in Spanish for an es browser', () => {
		preferLanguages(['es-ES']);
		const { sections } = view(pre());
		expect(sections.lastGames?.away.rows[0]).toMatchObject({
			resultLabel: 'G',
			opponent: 'vs DEN'
		});
		expect(sections.lastGames?.away.rows[1].opponent).toBe('@ PHX');
		expect(sections.seasonSeries?.summary).toBe('LAL lidera 1–0');
		expect(sections.seasonSeries?.meta).toBe('1 de 3 partidos jugados');
		expect(sections.seasonSeries?.games[1].date).toBe('Este partido');
	});
});
