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
		expect(hidden.sections).toEqual({
			highlights: null,
			score: null,
			winProbability: null,
			boxScore: null
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
