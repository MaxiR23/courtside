// web/tests/lib/feed/props.test.ts
//
// Tests for the props layer that turns the games feed into the home page props.
//
// Tested:
// - Seven days with today in the middle; today's games as hero games (with team codes) in feed order, without postponed and canceled games
// - Postponed and canceled games stay in the schedule; with only those, no hero games; a delayed game stays with its tip time
// - Tip time as "9:00 PM ET"; scheduled, live (Q3, OT, 2OT), final, delayed, postponed and canceled games
// - The winner of a final game, passed through
// - Leaders (display name split), stats, highlights with autoplay, the hero chip's full team name
// - A final game with pending or unavailable stats keeps its line score and highlights without leaders or stats
// - A guest team (outside the league) is marked guest on its team view, has no player to watch, and has a leader marked guest with no photo; a feed without the guest key maps as league
// - A game with a guest side is never a hero game, with or without a code; the league games stay
// - A guest side without a code maps to a team with a null code, and its leader to a team with a null code
// - Minutes since the feed was generated, never negative
// - Null network, no video platform name, no videos, a one-word display name
// - A feed without seven days, and a live game without its fields or a final game without its winner or stats availability, cannot be shown
//
// What is covered:
// - Pure logic on a recorded feed (tests/lib/feed/fixtures/games.json); no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/props.test.ts
//
// SEE: web/src/lib/feed/props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import type { GamesFeed } from '../../../src/lib/contract/games';
import { toHomeView, type HomeView } from '../../../src/lib/feed/props';
import type { ScheduleGame } from '../../../src/lib/schedule/types';

const feed = (): GamesFeed =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', 'games.json'), 'utf8')) as GamesFeed;
// 23:05 UTC on the day the feed was generated: 5 minutes after generatedAt.
const received = new Date('2026-10-04T23:05:00Z');
const options = { videoPlatformName: 'Video platform' };

function view(source: GamesFeed = feed(), opts = options): HomeView {
	const result = toHomeView(source, received, opts);
	if (!result) throw new Error('The fixture feed must be showable');
	return result;
}
const todayGame = (v: HomeView, id: string): ScheduleGame => {
	const found = v.days[3].games.find((g) => g.id === id);
	if (!found) throw new Error(`No game ${id}`);
	return found;
};

describe('toHomeView', () => {
	it('maps the seven days with today in the middle', () => {
		const v = view();
		expect(v.days).toHaveLength(7);
		expect(v.days[0].date).toEqual(new Date(2026, 9, 1));
		expect(v.today).toEqual(new Date(2026, 9, 4));
		expect(v.days[3].date).toEqual(v.today);
		expect(v.days.map((d) => d.games.length)).toEqual([1, 0, 1, 6, 2, 0, 0]);
	});

	it("maps today's games to hero games in feed order, without postponed and canceled games", () => {
		const v = view();
		expect(v.heroGames.map((g) => [g.id, g.status])).toEqual([
			['g-sched', 'tonight'],
			['g-live', 'live'],
			['g-final', 'final'],
			['g-delayed', 'delayed']
		]);
		expect(v.heroGames[0].arena).toBe('Los Angeles Arena');
		expect(v.heroGames[0].away.name).toBe('Warriors');
		expect(v.heroGames[0].home.name).toBe('Lakers');
		expect(v.heroGames[0].away.code).toBe('GSW');
		expect(v.heroGames[0].home.code).toBe('LAL');
	});

	it("keeps postponed and canceled games in today's schedule", () => {
		const v = view();
		expect(v.days[3].games).toHaveLength(6);
		expect(todayGame(v, 'g-postponed').status.state).toBe('postponed');
		expect(todayGame(v, 'g-canceled').status.state).toBe('canceled');
	});

	it('has no hero games when every game of the day is postponed or canceled', () => {
		const source = feed();
		source.days[3].games = source.days[3].games.filter(
			(g) => g.id === 'g-postponed' || g.id === 'g-canceled'
		);
		const v = view(source);
		expect(v.heroGames).toEqual([]);
		expect(v.days[3].games).toHaveLength(2);
	});

	it('keeps a delayed game in the hero with its original tip time', () => {
		const delayed = view().heroGames.find((g) => g.id === 'g-delayed');
		expect(delayed).toMatchObject({
			status: 'delayed',
			tipTime: '8:00 PM ET',
			arena: 'Chicago Arena'
		});
	});

	it('formats the tip time as 9:00 PM ET', () => {
		const v = view();
		expect(todayGame(v, 'g-sched').status).toMatchObject({
			state: 'scheduled',
			tipTime: '9:00',
			tipSuffix: 'PM ET'
		});
		expect(v.heroGames[0].tipTime).toBe('9:00 PM ET');
	});

	it('maps a scheduled game with its venue and players to watch', () => {
		const game = todayGame(view(), 'g-sched');
		expect(game.status).toMatchObject({ network: 'Courtside TV' });
		expect(game.details).toEqual({
			kind: 'scheduled',
			venue: 'Los Angeles Arena',
			playersToWatch: {
				away: {
					firstName: 'Stephen',
					lastName: 'Curry',
					teamCode: 'GSW',
					photo: 'https://example.com/photos/GSW.png'
				},
				home: {
					firstName: 'LeBron',
					lastName: 'James',
					teamCode: 'LAL',
					photo: 'https://example.com/photos/LAL.png'
				}
			}
		});
	});

	it('maps a live game with Q3 and its clock', () => {
		const game = view().days[4].games[0];
		expect(game.status).toEqual({
			state: 'live',
			period: 'Q3',
			clock: '4:12',
			awayScore: 78,
			homeScore: 74
		});
		expect(game.details?.kind).toBe('played');
	});

	it('labels period 5 OT and period 6 2OT', () => {
		expect(todayGame(view(), 'g-live').status).toMatchObject({ period: 'OT' });
		const source = feed();
		source.days[3].games[1].period = 6;
		expect(todayGame(view(source), 'g-live').status).toMatchObject({ period: '2OT' });
	});

	it('maps a final game with leaders, stats and highlights', () => {
		const game = todayGame(view(), 'g-final');
		expect(game.status).toEqual({
			state: 'final',
			awayScore: 112,
			homeScore: 104,
			winner: 'away'
		});
		if (game.details?.kind !== 'played') throw new Error('Expected played details');
		expect(game.details.periods).toEqual({ away: [30, 28, 26, 28], home: [24, 27, 25, 28] });
		expect(game.details.leaders.away).toEqual({
			firstName: 'Nikola',
			lastName: 'Jokic',
			photo: 'https://example.com/photos/DEN.png',
			team: { code: 'DEN', name: 'Nuggets', city: 'Denver', guest: false },
			points: 31,
			rebounds: 7,
			assists: 6
		});
		expect(game.details.stats.home).toEqual({
			fieldGoalPct: 0.452,
			threePointPct: 0.375,
			rebounds: 42,
			assists: 25,
			turnovers: 12
		});
		expect(game.details.highlights).toMatchObject({
			platform: 'Video platform',
			searchUrl: 'https://example.com/search?q=highlights'
		});
		expect(game.details.highlights?.videos).toHaveLength(2);
		expect(game.details.highlights?.videos[0]).toMatchObject({
			title: 'Full game highlights',
			channel: 'League Channel',
			thumbnail: 'https://example.com/thumbs/1.jpg'
		});
	});

	it("splits the leader's display name", () => {
		const game = todayGame(view(), 'g-live');
		if (game.details?.kind !== 'played') throw new Error('Expected played details');
		expect(game.details.leaders.home).toMatchObject({ firstName: 'Jalen', lastName: 'Brunson' });
	});

	it('keeps the rest of a longer display name as the last name', () => {
		const source = feed();
		const leaders = source.days[3].games[2].leaders;
		if (!leaders) throw new Error('fixture');
		leaders.away.displayName = 'Karl-Anthony Towns Jr.';
		const game = todayGame(view(source), 'g-final');
		if (game.details?.kind !== 'played') throw new Error('Expected played details');
		expect(game.details.leaders.away).toMatchObject({
			firstName: 'Karl-Anthony',
			lastName: 'Towns Jr.'
		});
	});

	it('builds the full team name for the hero chip', () => {
		const v = view();
		expect(v.heroGames[0].away.star).toEqual({
			firstName: 'Stephen',
			lastName: 'Curry',
			shortName: 'Curry',
			teamCode: 'GSW',
			teamName: 'Golden State Warriors',
			photo: 'https://example.com/photos/GSW.png'
		});
		expect(v.heroGames[0].home.star.teamName).toBe('Los Angeles Lakers');
	});

	it('sets autoplay on the embed URL', () => {
		const game = todayGame(view(), 'g-final');
		if (game.details?.kind !== 'played') throw new Error('Expected played details');
		const [first, second] = game.details.highlights?.videos ?? [];
		expect(first.embedUrl).toBe('https://example.com/embed/1?autoplay=1');
		expect(second.embedUrl).toBe('https://example.com/embed/2?rel=0&autoplay=1');
		expect(first.id).not.toBe(second.id);
	});

	it('computes the minutes since the feed was generated', () => {
		expect(view().updatedMinutesAgo).toBe(5);
	});

	it('never reports negative minutes', () => {
		const result = toHomeView(feed(), new Date('2026-10-04T22:00:00Z'), options);
		expect(result?.updatedMinutesAgo).toBe(0);
	});

	it('keeps a null network', () => {
		const game = view().days[4].games[1];
		expect(game.status).toMatchObject({ state: 'scheduled', network: null });
	});

	it('leaves highlights out without a video platform name', () => {
		const game = todayGame(view(feed(), {} as typeof options), 'g-final');
		if (game.details?.kind !== 'played') throw new Error('Expected played details');
		expect(game.details.highlights).toBeUndefined();
	});

	it('passes the winner through on a final game won by the home team', () => {
		const game = view().days[2].games.find((g) => g.id === 'g-final2');
		expect(game?.status).toMatchObject({ state: 'final', winner: 'home' });
	});

	it('returns null for a final game without its winner', () => {
		const source = feed();
		source.days[3].games[2].winner = null;
		expect(toHomeView(source, received, options)).toBeNull();
	});

	it.each(['pending', 'unavailable'] as const)(
		'maps a final game with %s stats to its line score and highlights without leaders or stats',
		(availability) => {
			const source = feed();
			const final = source.days[3].games[2];
			final.statsAvailability = availability;
			final.leaders = null;
			final.teamStats = null;
			const game = todayGame(view(source), 'g-final');
			if (game.details?.kind !== 'final-without-stats') throw new Error('Expected no stats');
			expect(game.details.statsAvailability).toBe(availability);
			expect(game.details.periods).toEqual({ away: [30, 28, 26, 28], home: [24, 27, 25, 28] });
			expect(game.details.highlights?.videos).toHaveLength(2);
			expect('leaders' in game.details).toBe(false);
			expect('stats' in game.details).toBe(false);
		}
	);

	it('returns null for a final game without its stats availability', () => {
		const source = feed();
		source.days[3].games[2].statsAvailability = null;
		expect(toHomeView(source, received, options)).toBeNull();
	});

	it('returns null for a final game from an older feed with no stats availability key', () => {
		const source = feed();
		delete (source.days[3].games[2] as Partial<GamesFeed['days'][0]['games'][0]>).statsAvailability;
		expect(toHomeView(source, received, options)).toBeNull();
	});

	it('maps a final game with no videos to the pending highlights', () => {
		const game = view().days[2].games[0];
		if (game.details?.kind !== 'played') throw new Error('Expected played details');
		expect(game.details.highlights).toEqual({
			platform: 'Video platform',
			searchUrl: 'https://example.com/search?q=highlights',
			videos: []
		});
	});

	it('maps delayed, postponed and canceled with no score and no details', () => {
		const v = view();
		for (const state of ['delayed', 'postponed', 'canceled'] as const) {
			const game = todayGame(v, `g-${state}`);
			expect(game.status).toEqual({ state });
			expect(game.details).toBeUndefined();
		}
	});

	it('a one-word display name', () => {
		const source = feed();
		const leaders = source.days[3].games[2].leaders;
		if (!leaders) throw new Error('fixture');
		leaders.home.displayName = 'Nene';
		const game = todayGame(view(source), 'g-final');
		if (game.details?.kind !== 'played') throw new Error('Expected played details');
		expect(game.details.leaders.home).toMatchObject({ firstName: 'Nene', lastName: '' });
	});

	it('returns null for a feed without seven days', () => {
		const source = feed();
		source.days.pop();
		expect(toHomeView(source, received, options)).toBeNull();
	});

	it('returns null for a live game without the fields its status requires', () => {
		const source = feed();
		source.days[3].games[1].score = null;
		expect(toHomeView(source, received, options)).toBeNull();
	});
});

describe('toHomeView with a guest team', () => {
	const guest = { code: 'HCM', name: 'Mariners', city: 'Harbor City', guest: true };

	function withGuests(): GamesFeed {
		const source = feed();
		const games = source.days[3].games;
		const scheduled = games[0];
		scheduled.away = guest;
		scheduled.stars.away = null;
		const final = games[2];
		final.away = guest;
		final.winner = 'away';
		final.stars.away = null;
		if (!final.leaders) throw new Error('fixture');
		final.leaders.away = { ...final.leaders.away, teamCode: 'HCM', photoUrl: null };
		return source;
	}

	it('marks a guest team and leaves a league team unmarked', () => {
		const game = todayGame(view(withGuests()), 'g-sched');
		expect(game.away).toEqual({ ...guest });
		expect(game.home.guest).toBe(false);
	});

	it('maps a feed without the guest key as league teams', () => {
		const game = todayGame(view(), 'g-sched');
		expect(game.away.guest).toBe(false);
		expect(game.home.guest).toBe(false);
	});

	it('has no player to watch for the guest side and keeps the league side', () => {
		const game = todayGame(view(withGuests()), 'g-sched');
		if (game.details?.kind !== 'scheduled') throw new Error('Expected scheduled details');
		expect(game.details.playersToWatch.away).toBeNull();
		expect(game.details.playersToWatch.home?.teamCode).toBe('LAL');
	});

	it('marks a guest leader and keeps its null photo', () => {
		const game = todayGame(view(withGuests()), 'g-final');
		if (game.details?.kind !== 'played') throw new Error('Expected played details');
		expect(game.details.leaders.away).toMatchObject({ team: guest, photo: null });
		expect(game.details.leaders.home.team.guest).toBe(false);
	});

	it('passes a guest winner through', () => {
		const game = todayGame(view(withGuests()), 'g-final');
		expect(game.status).toMatchObject({ state: 'final', winner: 'away' });
	});

	it('never puts a game with a guest side in the hero and keeps the league games', () => {
		const v = view(withGuests());
		expect(v.heroGames.map((g) => g.id)).toEqual(['g-live', 'g-delayed']);
		expect(v.days[3].games).toHaveLength(6);
	});
});

describe('toHomeView with a guest team without a code', () => {
	const codeless = { code: null, name: 'Mariners', city: 'Harbor City', guest: true };

	function withCodelessGuest(): GamesFeed {
		const source = feed();
		const final = source.days[3].games[2];
		final.away = codeless;
		final.winner = 'away';
		final.stars.away = null;
		if (!final.leaders) throw new Error('fixture');
		final.leaders.away = { ...final.leaders.away, teamCode: null, photoUrl: null };
		return source;
	}

	it('maps the guest side to a team with a null code', () => {
		const game = todayGame(view(withCodelessGuest()), 'g-final');
		expect(game.away).toEqual({ ...codeless });
		expect(game.status).toMatchObject({ state: 'final', winner: 'away' });
	});

	it('maps the leader of the guest to its team with a null code', () => {
		const game = todayGame(view(withCodelessGuest()), 'g-final');
		if (game.details?.kind !== 'played') throw new Error('Expected played details');
		expect(game.details.leaders.away.team).toEqual({ ...codeless });
	});

	it('does not put the game in the hero rotation', () => {
		const v = view(withCodelessGuest());
		expect(v.heroGames.map((g) => g.id)).not.toContain('g-final');
		expect(v.days[3].games).toHaveLength(6);
	});
});
