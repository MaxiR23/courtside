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
