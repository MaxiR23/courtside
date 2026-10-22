// web/tests/lib/feed/all-star-props.test.ts
//
// Tests for the All-Star props layer.
//
// Tested:
// - Sections per state, a section dropped without its data, and the order
// - Before: the Date, Venue and Format rows with and without values, the year plate, Last time only with
//   a previous edition and no MVP card without a previous MVP
// - Hero per state: tag, meta, kicker, title, score, stats read from the feed counts, buttons and plate kind
// - The default game is the feed's defaultGameId, in after, live and live between games
// - The live plate is the default game: live with the leading row in ink and the other muted, or the tip-off
//   plate; Next comes from isNext and is absent without it
// - Statuses: Final, Final · OT, live with the status text and clock as sent, "—", and the tip-off
// - A past edition's detail: no scheduled card, the "Highlights not available" placeholder and live false for a game that is not final; a current edition is unchanged
// - The selected game's detail: placeholders (final, live, scheduled), the venue strip with "—", Top 5 in
//   feed order, the scheduled card, leaders and team statistics
// - The box score: topPoints from the feed (a tie marks both, none marks none), negative plus-minus, a null
//   plus-minus as "—" that is not negative, a
//   player with no league team or photo, mobileMeta with "—"
// - Teams: placements, eliminated round, result rows from the feed with W, L and OT, a team-less Championship
// - A Top 5 value, a box score count and a shooting split the feed has as null show a dash (ADR 0055)
// - The MVP, the scoreline with the winner first, and 2, 3 and 4 team days
// - The previous view: the after view of previousEdition with the previous year, null without it
// - The edition video on the current, after and previous views, null without it; the Last time video URL; the season tag from the label passed in
//
// What is covered:
// - The format line from the parts in English and Spanish, and the round labels, the eliminated placement and the result rows in Spanish; an unknown round as sent (ADR 0054)
// - Recorded feeds (tests/lib/feed/fixtures/all-star-*.json) cloned and edited per case
// - The league mark of a box score row carries the feed's logo, and has no logo key without one
// - Every value is read from the feed field: nothing is counted or compared here
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/all-star-props.test.ts
//
// SEE: web/src/lib/feed/all-star-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { AllStarFeed, AllStarGame } from '../../../src/lib/contract/all-star';
import { toAllStarView } from '../../../src/lib/feed/all-star-props';
import { preferLanguages } from '../../prefer-languages';

afterEach(() => {
	vi.restoreAllMocks();
});

const fixture = (name: 'before' | 'live' | 'after'): AllStarFeed =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', `all-star-${name}.json`), 'utf8'));
const before = () => fixture('before');
const live = () => fixture('live');
const after = () => fixture('after');
const current = (feed: AllStarFeed) => toAllStarView(feed, 'current')!;
const game = (feed: AllStarFeed, id: string): AllStarGame =>
	feed.edition.games.find((g) => g.id === id)!;

describe('sections', () => {
	it('has Last time alone before, when there is a previous edition', () => {
		expect(current(before()).sections).toEqual(['last-time']);
	});

	it('has no section before without a previous edition', () => {
		const feed = before();
		feed.previous = null;
		feed.previousEdition = null;
		const view = current(feed);
		expect(view.sections).toEqual([]);
		expect(view.lastTime).toBeNull();
		expect(view.header.buttons).toEqual([]);
	});

	it('has the games and the teams while live, and the MVP, games and teams after', () => {
		expect(current(live()).sections).toEqual(['games', 'teams']);
		expect(current(after()).sections).toEqual(['mvp', 'games', 'teams']);
	});

	it('keeps the MVP section with the scoreline alone when the MVP is missing', () => {
		const feed = after();
		feed.mvp = null;
		const view = current(feed);
		expect(view.sections).toEqual(['mvp', 'games', 'teams']);
		expect(view.mvp).toBeNull();
		expect(view.scoreline).not.toBeNull();
	});

	it('drops the MVP section with no MVP and no final Championship, and keeps the order', () => {
		const feed = after();
		feed.mvp = null;
		feed.edition.games = feed.edition.games.filter((g) => !g.championship);
		feed.edition.counts.games = 3;
		expect(current(feed).sections).toEqual(['games', 'teams']);
	});

	it('drops a section with no data', () => {
		const feed = live();
		feed.edition.teams = [];
		expect(current(feed).sections).toEqual(['games']);
	});

	it('has the MVP section only after', () => {
		const feed = live();
		feed.mvp = after().mvp;
		expect(current(feed).mvp).toBeNull();
	});
});

describe('hero, before', () => {
	it('shows the date, venue and format rows with a value or "To be confirmed"', () => {
		const header = current(before()).header;
		expect(header.tag).toBe('All-Star 2027');
		expect(header.kicker).toBe('Next edition');
		expect(header.title).toBe('All-Star');
		expect(header.rows).toEqual([
			{ key: 'date', label: 'Date', value: 'Feb 14, 2027' },
			{ key: 'venue', label: 'Venue', value: 'Example Arena, Exampleton' },
			{ key: 'format', label: 'Format', value: 'To be confirmed' }
		]);
		expect(header.stats).toEqual([]);
		expect(header.buttons).toEqual([{ key: 'last-time', label: 'Last edition', primary: true }]);
		expect(header.plate).toEqual({ kind: 'year', year: '2027' });
	});

	it('reads "To be confirmed" for every row of an edition nothing is known about', () => {
		const feed = before();
		feed.edition.date = null;
		feed.edition.venue = null;
		const rows = current(feed).header.rows;
		expect(rows.map((r) => r.value)).toEqual([
			'To be confirmed',
			'To be confirmed',
			'To be confirmed'
		]);
	});

	it('shows the venue name alone when the city is missing, and the format line when known', () => {
		const feed = before();
		feed.edition.venue = { name: 'Example Arena', city: null, photoUrl: null };
		feed.edition.format = { targetPoints: 40, untimed: true, periods: null, minutes: null };
		const rows = current(feed).header.rows;
		expect(rows[1].value).toBe('Example Arena');
		expect(rows[2].value).toBe('First to 40 · Untimed');
	});
});

describe('Last time', () => {
	it('has the champion card, the MVP card and the link to the previous edition', () => {
		const last = current(before()).lastTime!;
		expect(last.champion).toEqual({
			kicker: 'Champions of the day',
			name: 'Team Dunes',
			meta: 'Feb 15 · Example Arena',
			score: '22–20'
		});
		expect(last.mvp).toMatchObject({ playerId: '4001', name: 'Gus Imagined' });
		expect(last.mvp?.summary).toBe('24 PTS · across 2 games');
		expect(last.link).toBe('Every game, box score and highlight from 2026 →');
	});

	it('has no MVP card when the previous edition has no MVP', () => {
		const feed = before();
		feed.previous!.mvp = null;
		const last = current(feed).lastTime!;
		expect(last.mvp).toBeNull();
		expect(last.champion.name).toBe('Team Dunes');
	});

	it('is not drawn while live or after', () => {
		const feed = live();
		feed.previous = before().previous;
		expect(current(feed).lastTime).toBeNull();
		expect(current(after()).lastTime).toBeNull();
	});
});

describe('hero, after', () => {
	it('has the champion, the Championship score and the stats from the feed counts', () => {
		const feed = after();
		const header = current(feed).header;
		expect(header.tag).toBe('All-Star 2027');
		expect(header.meta).toBe('Feb 14 · Example Arena');
		expect(header.kicker).toBe('Champions of the day');
		expect(header.title).toBe('Team Stripes');
		expect(header.score).toBe('25–23');
		expect(header.stats).toEqual([
			{ key: 'games', label: 'Games', value: '4', accent: false, countTo: 4 },
			{ key: 'teams', label: 'Teams', value: '3', accent: false, countTo: 3 },
			{ key: 'championship', label: 'Championship', value: '25–23', accent: true, countTo: null },
			{ key: 'attendance', label: 'Attendance', value: '18,500', accent: false, countTo: 18500 }
		]);
		expect(header.buttons.map((b) => [b.key, b.label, b.primary])).toEqual([
			['games', 'Every game', true],
			['mvp', 'All-Star MVP', false]
		]);
	});

	it('reads the stats from counts and not from the lists', () => {
		const feed = after();
		feed.edition.counts = { games: 9, teams: 8, final: 9, live: 0 };
		const stats = current(feed).header.stats;
		expect(stats[0].value).toBe('9');
		expect(stats[1].value).toBe('8');
	});

	it('has the MVP plate with its labels, or the score plate without an MVP', () => {
		expect(current(after()).header.plate).toEqual({
			kind: 'mvp',
			name: 'Ada Example',
			photo: 'https://example.com/photos/1001.png',
			jersey: '7',
			labels: '41 PTS · 3 games'
		});
		const feed = after();
		feed.mvp = null;
		const plate = current(feed).header.plate;
		expect(plate.kind).toBe('score');
		expect(feed.mvp).toBeNull();
		expect(current(feed).header.buttons.map((b) => b.key)).toEqual(['games']);
	});

	it('shows "—" for the score and the attendance when the Championship has none', () => {
		const feed = after();
		const final = game(feed, 'g4');
		final.attendance = null;
		feed.edition.games = [feed.edition.games[0], feed.edition.games[1], feed.edition.games[2]];
		feed.edition.teams.forEach((t) => (t.placement = { kind: 'so_far', roundLabel: null }));
		feed.mvp = null;
		const header = current(feed).header;
		expect(header.title).toBe('All-Star');
		expect(header.score).toBeNull();
		expect(header.stats[2].value).toBe('—');
		expect(header.stats[3].value).toBe('—');
		expect(header.plate.kind).toBe('year');
	});
});

describe('hero, live', () => {
	it('has the stats from the feed counts and the live plate', () => {
		const header = current(live()).header;
		expect(header.kicker).toBe('Live now');
		expect(header.title).toBe('All-Star');
		expect(header.score).toBeNull();
		expect(header.stats.map((s) => [s.label, s.value, s.accent])).toEqual([
			['Games today', '3', false],
			['Final', '1', false],
			['Live now', '1', true],
			['Teams', '4', false]
		]);
		expect(header.buttons).toEqual([{ key: 'games', label: 'Follow the games', primary: true }]);
	});

	it('reads the stats from counts and not from the lists', () => {
		const feed = live();
		feed.edition.counts = { games: 7, teams: 6, final: 5, live: 2 };
		expect(current(feed).header.stats.map((s) => s.value)).toEqual(['7', '5', '2', '6']);
	});

	it('shows the game of defaultGameId on the plate, with the leading team in ink and the other muted', () => {
		const plate = current(live()).header.plate;
		expect(plate).toMatchObject({
			kind: 'live',
			gameId: 's2',
			header: 'Live · Semifinals',
			formatLine: '1 period · 12 min',
			clock: '5:12',
			status: 'Q1',
			next: 'Next: Championship'
		});
		if (plate.kind !== 'live') throw new Error('not live');
		expect(plate.rows.map((r) => [r.name, r.score, r.winner, r.loser])).toEqual([
			['Team Peaks', '30', true, false],
			['Team Dunes', '12', false, true]
		]);
	});

	it('mutes neither row when leading is null', () => {
		const feed = live();
		game(feed, 's2').leading = null;
		const plate = current(feed).header.plate;
		if (plate.kind !== 'live') throw new Error('not live');
		expect(plate.rows.every((r) => !r.winner && !r.loser)).toBe(true);
	});

	it('mutes the home row when the feed says home leads, whatever the scores', () => {
		const feed = live();
		game(feed, 's2').leading = 'home';
		const plate = current(feed).header.plate;
		if (plate.kind !== 'live') throw new Error('not live');
		expect(plate.rows.map((r) => r.loser)).toEqual([true, false]);
	});

	it('has no Next without a next game and shows "—" for a missing clock', () => {
		const feed = live();
		game(feed, 'c1').isNext = false;
		game(feed, 's2').clock = null;
		game(feed, 's2').statusText = null;
		const plate = current(feed).header.plate;
		if (plate.kind !== 'live') throw new Error('not live');
		expect(plate.next).toBeNull();
		expect(plate.clock).toBe('—');
		expect(plate.status).toBeNull();
	});

	it('names the next game by its matchup when it has no round label', () => {
		const feed = live();
		const next = game(feed, 'c1');
		next.roundLabel = null;
		const plate = current(feed).header.plate;
		if (plate.kind !== 'live') throw new Error('not live');
		expect(plate.next).toBe('Next: To be determined');
	});

	it('shows the tip-off plate of the default game between games', () => {
		const feed = live();
		game(feed, 's2').status = 'final';
		game(feed, 's2').score = { away: 30, home: 12 };
		game(feed, 's2').winner = 'away';
		game(feed, 's2').leading = null;
		feed.edition.defaultGameId = 'c1';
		feed.edition.counts = { games: 3, teams: 4, final: 2, live: 0 };
		const view = current(feed);
		expect(view.defaultGame).toBe('c1');
		expect(view.header.plate).toEqual({
			kind: 'tipoff',
			gameId: 'c1',
			text: 'Tip-off · 8:20 PM ET'
		});
	});
});

describe('the default game', () => {
	it('is the defaultGameId of the feed in each state', () => {
		expect(current(after()).defaultGame).toBe('g4');
		expect(current(live()).defaultGame).toBe('s2');
		expect(current(before()).defaultGame).toBeNull();
	});

	it('is whatever the feed sends, not a rule of this layer', () => {
		const feed = after();
		feed.edition.defaultGameId = 'g1';
		expect(current(feed).defaultGame).toBe('g1');
	});
});

describe('game cards and statuses', () => {
	it('has one card per game in feed order with the round tag and the matchup', () => {
		const cards = current(after()).games;
		expect(cards.map((c) => c.id)).toEqual(['g1', 'g2', 'g3', 'g4']);
		expect(cards[0].round).toEqual({ text: 'Round Robin', championship: false });
		expect(cards[3].round).toEqual({ text: 'Championship', championship: true });
		expect(cards[0].label).toBe('STR · WAV');
	});

	it('shows Final, and Final · OT on an overtime game', () => {
		const cards = current(after()).games;
		expect(cards[0].status).toEqual({ kind: 'final', text: 'Final' });
		expect(cards[1].status).toEqual({ kind: 'final', text: 'Final · OT' });
	});

	it('shows the live status text and the clock as sent', () => {
		const cards = current(live()).games;
		expect(cards[1].status).toEqual({ kind: 'live', text: 'Live · Q1 · 5:12' });
	});

	it('shows only the part the feed sends, and "—" when it sends neither', () => {
		const feed = live();
		const target = game(feed, 's2');
		target.clock = null;
		expect(current(feed).games[1].status.text).toBe('Live · Q1');
		target.statusText = null;
		target.clock = '3:00';
		expect(current(feed).games[1].status.text).toBe('Live · 3:00');
		target.clock = null;
		expect(current(feed).games[1].status.text).toBe('Live · —');
	});

	it('shows the tip-off time of a game not started', () => {
		expect(current(live()).games[2].status).toEqual({ kind: 'tipoff', text: '8:20 PM ET' });
	});

	it('mutes the loser and marks the winner of a final game', () => {
		const rows = current(after()).games[0].rows;
		expect(rows.map((r) => [r.name, r.score, r.winner, r.loser])).toEqual([
			['Team Stripes', '21', true, false],
			['Team Waves', '18', false, true]
		]);
	});

	it('shows "To be determined" rows with no team for a team-less Championship', () => {
		const card = current(live()).games[2];
		expect(card.label).toBe('To be determined');
		expect(card.rows).toEqual([
			{ team: null, name: 'To be determined', score: '—', winner: false, loser: false },
			{ team: null, name: 'To be determined', score: '—', winner: false, loser: false }
		]);
	});

	it('shows no round tag for a game with no round label', () => {
		const feed = after();
		game(feed, 'g1').roundLabel = null;
		expect(current(feed).games[0].round).toBeNull();
	});
});

describe('the detail of a game', () => {
	it('has the video of a stored highlight and no placeholder', () => {
		const detail = current(after()).details.g4;
		expect(detail.video).toMatchObject({
			title: 'Example highlights',
			embedUrl: 'https://example.com/embed/g?autoplay=1'
		});
		expect(detail.placeholder).toBeNull();
	});

	it('has "Highlights not available" for a final game without highlights', () => {
		const detail = current(after()).details.g1;
		expect(detail.video).toBeNull();
		expect(detail.placeholder).toBe('Highlights not available');
		expect(detail.live).toBe(false);
	});

	it('has the after-the-buzzer text for a live game and a muted button', () => {
		const detail = current(live()).details.s2;
		expect(detail.placeholder).toBe('Highlights post after the final buzzer');
		expect(detail.live).toBe(true);
	});

	it('shows no live element in a past edition: no scheduled card, the unavailable placeholder, not live', () => {
		const past = toAllStarView(live(), 'current', { pastLabel: '2024-25' })!;
		expect(past.details.c1.scheduled).toBeNull();
		expect(past.details.c1.placeholder).toBe('Highlights not available');
		expect(past.details.c1.live).toBe(false);
		expect(past.details.s2.placeholder).toBe('Highlights not available');
		expect(past.details.s2.live).toBe(false);
		expect(current(live()).details.s2.live).toBe(true);
		expect(current(live()).details.c1.scheduled).not.toBeNull();
	});

	it('keeps the video of a past edition game that has one', () => {
		const past = toAllStarView(after(), 'current', { pastLabel: '2024-25' })!;
		expect(past.details.g4.video).not.toBeNull();
		expect(past.details.g4.placeholder).toBeNull();
	});

	it('has the one centered card for a game not started', () => {
		const detail = current(live()).details.c1;
		expect(detail.scheduled).toEqual({
			title: 'Tip-off · 8:20 PM ET',
			body: 'Box score, leaders and highlights appear once the game starts.'
		});
		expect(current(live()).details.s2.scheduled).toBeNull();
	});

	it('has the venue strip with its values, and "—" for the ones the feed lacks', () => {
		expect(current(after()).details.g4.venueStrip).toEqual([
			{ key: 'venue', label: 'Venue', value: 'Example Arena, Exampleton' },
			{ key: 'attendance', label: 'Attendance', value: '18,500' },
			{ key: 'broadcast', label: 'Broadcast', value: 'Example Network · Example Stream' },
			{ key: 'tipoff', label: 'Tip-off', value: '8:50 PM ET' }
		]);
		const strip = current(live()).details.c1.venueStrip;
		expect(strip[1].value).toBe('—');
		expect(strip[2].value).toBe('—');
	});

	it('shows only the TV name when there is no streaming broadcast', () => {
		const feed = after();
		game(feed, 'g4').broadcasts = [{ name: 'Example Network', kind: 'tv' }];
		expect(current(feed).details.g4.venueStrip[2].value).toBe('Example Network');
	});

	it('has the Top 5 rows in feed order with the team line and the league bar', () => {
		const rows = current(after()).details.g4.top5;
		expect(rows.map((r) => [r.rank, r.name, r.points])).toEqual([
			['#1', 'Ada Example', '16'],
			['#2', 'Cy Placeholder', '14'],
			['#3', 'Dee Invented', '9'],
			['#4', 'Ben Sample', '9']
		]);
		expect(rows[0]).toMatchObject({
			top: true,
			teamLine: 'Team Stripes · HBR',
			line: 'PTS · 4 REB · 3 AST'
		});
		expect(rows[2]).toMatchObject({ photo: null, top: false });
	});

	it('shows a dash for a Top 5 value, a box score count and a shooting split the feed has as null', () => {
		const feed = after();
		Object.assign(game(feed, 'g4').top5[0]!, { points: null, rebounds: null });
		const player = game(feed, 'g1').boxScore!.away.players[0];
		Object.assign(player, { points: null, fieldGoalsMade: null, fieldGoalsAttempted: null });
		const top = current(feed).details.g4.top5[0];
		expect(top.points).toBe('—');
		expect(top.line).toContain('—');
		const row = current(feed).boxes.g1!.away.rows[0];
		expect([row.points, row.fieldGoals]).toEqual(['—', '—']);
	});

	it('keeps the order the feed sends for the Top 5', () => {
		const feed = after();
		game(feed, 'g4').top5.reverse();
		expect(current(feed).details.g4.top5[0].name).toBe('Ben Sample');
	});

	it('has no league line or monogram for a player the feed cannot place', () => {
		const rows = current(live()).details.s2.top5;
		expect(rows[0]).toMatchObject({ name: 'Eli Made-Up', league: null, teamLine: 'Team Peaks' });
	});

	it('has the leaders and the six team statistics with the feed better side', () => {
		const detail = current(after()).details.g4;
		expect(detail.leaders?.away).toMatchObject({ firstName: 'Ada', points: 16 });
		expect(detail.teamStats?.map((s) => s.label)).toEqual([
			'FG%',
			'3PM',
			'Rebounds',
			'Assists',
			'Steals',
			'Blocks'
		]);
		const [fg, , , , steals, blocks] = detail.teamStats!;
		expect(fg).toMatchObject({ away: '50.0%', home: '40.0%', better: 'away' });
		expect(steals).toMatchObject({ better: null, awayShare: 1, homeShare: 1 });
		expect(blocks).toMatchObject({
			away: '0',
			home: '1',
			awayShare: 0,
			homeShare: 1,
			better: 'home'
		});
	});

	it('has no leaders and no statistics when the feed has none', () => {
		const feed = after();
		game(feed, 'g1').leaders = null;
		game(feed, 'g1').teamStats = null;
		const detail = current(feed).details.g1;
		expect(detail.leaders).toBeNull();
		expect(detail.teamStats).toBeNull();
	});

	it('shows 0 shares when both values are 0', () => {
		const feed = after();
		const stat = game(feed, 'g1').teamStats![5];
		stat.away = 0;
		stat.home = 0;
		stat.better = null;
		expect(current(feed).details.g1.teamStats![5]).toMatchObject({ awayShare: 0, homeShare: 0 });
	});

	it('has the scoreboard rows and status', () => {
		const board = current(after()).details.g2.scoreboard;
		expect(board.status).toBe('Final · OT');
		expect(board.rows.map((r) => r.score)).toEqual(['17', '20']);
	});
});

describe('the box score', () => {
	it('has a tab per All-Star team and a row per player in feed order', () => {
		const box = current(after()).boxes.g1!;
		expect(box.away.tab).toBe('STR');
		expect(box.home.tab).toBe('WAV');
		expect(box.away.rows.map((r) => r.name)).toEqual(['Ada Example', 'Ben Sample']);
		expect(box.away.rows[0]).toMatchObject({
			jersey: '7',
			position: 'G',
			minutes: '10:00',
			points: '12',
			fieldGoals: '6-9',
			threePoints: '1-3',
			plusMinus: '+5',
			starter: true,
			mobileMeta: '#7 · G · 10:00'
		});
	});

	it('takes topPoints from the feed, and a tie marks both rows', () => {
		const box = current(after()).boxes.g1!;
		expect(box.away.rows.map((r) => r.topPoints)).toEqual([true, true]);
		expect(box.home.rows.map((r) => r.topPoints)).toEqual([true, false]);
	});

	it('marks nobody when the feed marks nobody, whatever the points', () => {
		const feed = after();
		game(feed, 'g1').boxScore!.home.players.forEach((p) => (p.topPoints = false));
		expect(current(feed).boxes.g1!.home.rows.some((r) => r.topPoints)).toBe(false);
	});

	it('mutes a negative plus-minus', () => {
		const rows = current(after()).boxes.g1!.away.rows;
		expect(rows.map((r) => r.negative)).toEqual([false, true]);
		expect(rows[1].plusMinus).toBe('-3');
	});

	it('shows a dash for a null plus-minus and does not mute it', () => {
		const feed = after();
		game(feed, 'g1').boxScore!.away.players[1].plusMinus = null;
		const rows = current(feed).boxes.g1!.away.rows;
		expect(rows[1].plusMinus).toBe('—');
		expect(rows[1].negative).toBe(false);
	});

	it('has no league monogram for a player with no league team, and "—" for missing parts', () => {
		const rows = current(after()).boxes.g2!.away.rows;
		expect(rows[0]).toMatchObject({
			name: 'Eli Made-Up',
			league: null,
			jersey: '—',
			position: '—',
			mobileMeta: '— · — · 10:00'
		});
	});

	it('has a player without a photo as null', () => {
		const rows = current(after()).boxes.g1!.home.rows;
		expect(rows[1]).toMatchObject({ name: 'Dee Invented', photo: null });
	});

	it('has the league colors of a player the feed placed', () => {
		const row = current(after()).boxes.g1!.away.rows[0];
		expect(row.league).toEqual({
			code: 'HBR',
			team: { code: 'HBR', name: null, city: null, guest: false },
			primary: '#1d428a',
			secondary: '#ffc72c'
		});
	});

	it('has the totals row', () => {
		expect(current(after()).boxes.g1!.away.totals).toEqual({
			points: '24',
			rebounds: '9',
			assists: '4',
			steals: '2',
			blocks: '0',
			fieldGoals: '12-18',
			threePoints: '2-6'
		});
	});

	it('is null for a game with no box score', () => {
		const view = current(live());
		expect(view.boxes.c1).toBeNull();
		expect(view.boxes.s2).not.toBeNull();
	});

	it('shows "—" for a missing minutes value', () => {
		const feed = after();
		game(feed, 'g1').boxScore!.away.players[0].minutes = '';
		expect(current(feed).boxes.g1!.away.rows[0].minutes).toBe('—');
	});
});

describe('the MVP and the scoreline', () => {
	it('has one line per game with the result, the Championship flagged, and the day total', () => {
		const mvp = current(after()).mvp!;
		expect(mvp).toMatchObject({
			playerId: '1001',
			name: 'Ada Example',
			total: '41 PTS · across 3 games',
			league: { code: 'HBR' }
		});
		expect(mvp.lines.map((l) => [l.round, l.championship, l.result, l.stat])).toEqual([
			['Round Robin', false, 'W 21–18 vs Team Waves', '12 PTS · 4 REB · 3 AST'],
			['Round Robin', false, 'W 20–17 vs Team Peaks', '13 PTS · 2 REB · 2 AST'],
			['Championship', true, 'W 25–23 vs Team Waves', '16 PTS · 4 REB · 3 AST']
		]);
	});

	it('shows a loss line as L', () => {
		const feed = after();
		feed.mvp!.lines[0].result = 'loss';
		expect(current(feed).mvp!.lines[0].result.startsWith('L ')).toBe(true);
	});

	it('has the scoreline with the winner first', () => {
		const line = current(after()).scoreline!;
		expect(line.gameId).toBe('g4');
		expect(line.rows.map((r) => [r.name, r.score, r.winner])).toEqual([
			['Team Stripes', '25', true],
			['Team Waves', '23', false]
		]);
	});

	it('puts the home winner first', () => {
		const feed = after();
		const final = game(feed, 'g4');
		final.score = { away: 20, home: 24 };
		final.winner = 'home';
		const line = current(feed).scoreline!;
		expect(line.rows.map((r) => r.name)).toEqual(['Team Waves', 'Team Stripes']);
		expect(current(feed).header.score).toBe('24–20');
	});

	it('has no scoreline when the Championship is not final', () => {
		expect(current(live()).scoreline).toBeNull();
	});
});

describe('the teams', () => {
	it('has one card per team: 3 after and 4 while live', () => {
		expect(current(after()).teams.map((t) => t.key)).toEqual(['STR', 'WAV', 'PKS']);
		expect(current(live()).teams).toHaveLength(4);
	});

	it('has the placement of each team and the round of an eliminated one', () => {
		const teams = current(after()).teams;
		expect(teams.map((t) => t.placement)).toEqual([
			'Champion',
			'Runner-up',
			'Eliminated in the Round Robin'
		]);
		expect(teams.map((t) => t.champion)).toEqual([true, false, false]);
		const live4 = current(live()).teams;
		expect(live4.map((t) => t.placement)).toEqual([
			'So far today',
			'So far today',
			'Yet to play',
			'Yet to play'
		]);
	});

	it('has the record and the result rows from the feed with W, L and OT', () => {
		const [stripes, , peaks] = current(after()).teams;
		expect(stripes.record).toBe('3–0');
		expect(stripes.results.map((r) => [r.mark, r.text, r.score, r.win])).toEqual([
			['W', 'Round Robin · vs WAV', '21–18', true],
			['W', 'Round Robin · vs PKS · OT', '20–17', true],
			['W', 'Championship · vs WAV', '25–23', true]
		]);
		expect(peaks.record).toBe('0–2');
		expect(peaks.results.map((r) => r.mark)).toEqual(['L', 'L']);
	});

	it('reads the rows from the results, not from the games', () => {
		const feed = after();
		feed.edition.teams[0].results = [];
		expect(current(feed).teams[0].results).toEqual([]);
	});

	it('has the roster tiles with a title, and a player with no league team titled by name', () => {
		const peaks = current(after()).teams[2];
		expect(peaks.roster.map((t) => t.title)).toEqual(['Eli Made-Up', 'Fay Sketch · HBR']);
		expect(peaks.roster[0]).toMatchObject({ league: null });
		expect(peaks.roster[1].league?.code).toBe('HBR');
	});

	it('has 2 teams on a two-team day', () => {
		const view = toAllStarView(after(), 'previous')!;
		expect(view.teams.map((t) => t.key)).toEqual(['DNS', 'PKS']);
	});

	it('shows "—" for the round of an eliminated team the feed gave no label', () => {
		const feed = after();
		feed.edition.teams[2].placement.roundLabel = null;
		expect(current(feed).teams[2].placement).toBe('Eliminated in the —');
	});

	it('uses the name for a team with no code', () => {
		const feed = after();
		feed.edition.teams[0].team.code = null;
		expect(current(feed).teams[0]).toMatchObject({ key: 'Team Stripes', name: 'Team Stripes' });
	});
});

describe('the previous view', () => {
	it('is the after view of previousEdition with the year of previous', () => {
		const view = toAllStarView(before(), 'previous')!;
		expect(view.header.state).toBe('after');
		expect(view.header.tag).toBe('All-Star 2026');
		expect(view.header.title).toBe('Team Dunes');
		expect(view.header.score).toBe('22–20');
		expect(view.sections).toEqual(['mvp', 'games', 'teams']);
		expect(view.lastTime).toBeNull();
		expect(view.mvp?.name).toBe('Gus Imagined');
		expect(view.defaultGame).toBe('p2');
		expect(view.header.stats.map((s) => s.value)).toEqual(['2', '2', '22–20', '17,250']);
	});

	it('reads the counts and default game of previousEdition', () => {
		const feed = before();
		feed.previousEdition!.counts = { games: 5, teams: 4, final: 5, live: 0 };
		feed.previousEdition!.defaultGameId = 'p1';
		const view = toAllStarView(feed, 'previous')!;
		expect(view.defaultGame).toBe('p1');
		expect(view.header.stats.slice(0, 2).map((s) => s.value)).toEqual(['5', '4']);
	});

	it('has the overtime Championship in its scoreline and its highlights', () => {
		const view = toAllStarView(before(), 'previous')!;
		expect(view.scoreline).toMatchObject({ gameId: 'p2', overtime: true });
		expect(view.details.p2.video).not.toBeNull();
	});

	it('is null when the feed has no previous edition', () => {
		const feed = before();
		feed.previousEdition = null;
		expect(toAllStarView(feed, 'previous')).toBeNull();
		feed.previous = null;
		expect(toAllStarView(feed, 'previous')).toBeNull();
	});

	it('draws the previous edition whatever the state of the current one', () => {
		const feed = after();
		feed.previous = before().previous;
		feed.previousEdition = before().previousEdition;
		expect(toAllStarView(feed, 'previous')?.header.tag).toBe('All-Star 2026');
	});
});

const highlight = (name: string) => ({
	title: `${name} highlights`,
	channel: 'Example Channel',
	thumbnailUrl: `https://video.example.com/thumb/${name}.jpg`,
	embedUrl: `https://video.example.com/embed/${name}`
});

describe('the edition video', () => {
	it('is the edition highlight of an after feed, with the autoplay embed, and null without it', () => {
		const feed = after();
		feed.edition.editionHighlight = highlight('edition');
		expect(current(feed).editionVideo).toEqual({
			id: 'https://video.example.com/embed/edition',
			title: 'edition highlights',
			channel: 'Example Channel',
			thumbnail: 'https://video.example.com/thumb/edition.jpg',
			embedUrl: 'https://video.example.com/embed/edition?autoplay=1'
		});
		feed.edition.editionHighlight = null;
		expect(current(feed).editionVideo).toBeNull();
		delete (feed.edition as { editionHighlight?: unknown }).editionHighlight;
		expect(current(feed).editionVideo).toBeNull();
	});

	it('is the highlight of previousEdition on the previous view, and null without it', () => {
		const feed = before();
		feed.previousEdition!.editionHighlight = highlight('earlier');
		expect(toAllStarView(feed, 'previous')!.editionVideo?.title).toBe('earlier highlights');
		feed.previousEdition!.editionHighlight = null;
		expect(toAllStarView(feed, 'previous')!.editionVideo).toBeNull();
	});
});

describe('the Last time video', () => {
	it('is the embed URL of the previous edition highlight, null without it', () => {
		const feed = before();
		feed.previous!.editionHighlight = highlight('last');
		expect(current(feed).lastTime?.video).toBe('https://video.example.com/embed/last');
		feed.previous!.editionHighlight = null;
		expect(current(feed).lastTime?.video).toBeNull();
	});
});

describe('the season tag', () => {
	it('is built from the label passed in and null without it', () => {
		expect(toAllStarView(after(), 'current', { pastLabel: '2004-05' })!.header.seasonTag).toBe(
			'Season 2004-05'
		);
		expect(current(after()).header.seasonTag).toBeNull();
	});

	it('is on every state of the header', () => {
		for (const feed of [before(), live(), after()]) {
			expect(toAllStarView(feed, 'current', { pastLabel: '2004-05' })!.header.seasonTag).toBe(
				'Season 2004-05'
			);
		}
	});

	it('is written in Spanish', () => {
		preferLanguages(['es']);
		expect(toAllStarView(after(), 'current', { pastLabel: '2004-05' })!.header.seasonTag).toBe(
			'Temporada 2004-05'
		);
	});
});

describe('the format line from the parts', () => {
	const withFormat = (format: AllStarFeed['edition']['format']) => {
		const feed = before();
		feed.edition.format = format;
		return current(feed).header.rows[2].value;
	};

	it('words a target score, untimed and periods in English', () => {
		expect(withFormat({ targetPoints: 40, untimed: true, periods: null, minutes: null })).toBe(
			'First to 40 · Untimed'
		);
		expect(withFormat({ targetPoints: 40, untimed: false, periods: null, minutes: null })).toBe(
			'First to 40'
		);
		expect(withFormat({ targetPoints: null, untimed: false, periods: 1, minutes: 12 })).toBe(
			'1 period · 12 min'
		);
		expect(withFormat({ targetPoints: null, untimed: false, periods: 4, minutes: 12 })).toBe(
			'4 periods · 12 min'
		);
	});

	it('words them in Spanish with the comma of the language', () => {
		preferLanguages(['es']);
		expect(withFormat({ targetPoints: 40, untimed: true, periods: null, minutes: null })).toBe(
			'A 40 puntos · Sin reloj'
		);
		expect(withFormat({ targetPoints: null, untimed: false, periods: 1, minutes: 12 })).toBe(
			'1 periodo · 12 min'
		);
		expect(withFormat({ targetPoints: null, untimed: false, periods: 4, minutes: 1.5 })).toBe(
			'4 periodos · 1,5 min'
		);
	});

	it('says to be confirmed for no format', () => {
		expect(withFormat(null)).toBe('To be confirmed');
	});
});

describe('the position in Spanish', () => {
	it('translates a position name in the box row and its mobile meta, and keeps an abbreviation', () => {
		const feed = after();
		const row = feed.edition.games[0].boxScore!.away.players[0];
		row.position = 'Guard';
		preferLanguages(['es']);
		const rows = current(feed).boxes[feed.edition.games[0].id]!.away.rows;
		expect(rows[0].position).toBe('Escolta');
		expect(rows[0].mobileMeta).toContain('Escolta');
		expect(rows[1].position).toBe('F');
	});
});

describe('the round labels in Spanish', () => {
	it('translates the round of a card, the eliminated placement and the result rows', () => {
		preferLanguages(['es']);
		const view = current(after());
		expect(view.games.map((g) => g.round?.text)).toContain('Todos contra todos');
		expect(view.teams[2].placement).toBe('Eliminado en Todos contra todos');
		expect(view.teams[0].results[0].text).toContain('Todos contra todos');
	});

	it('shows an unknown round as sent', () => {
		const feed = after();
		feed.edition.games[0].roundLabel = 'Skills Challenge';
		preferLanguages(['es']);
		expect(current(feed).games[0].round?.text).toBe('Skills Challenge');
	});
});

describe('the league mark', () => {
	it("carries the feed's logo, and leaves the key out when the feed has none", () => {
		const source = after();
		const row = () => current(source).boxes.g1!.away.rows[0]!;
		expect('logo' in row().league!.team).toBe(false);
		game(source, 'g1').boxScore!.away.players[0]!.leagueTeam!.logo = {
			light: 'https://example.com/hbr-light.svg',
			dark: null
		};
		expect(row().league!.team.logo).toEqual({
			light: 'https://example.com/hbr-light.svg',
			dark: null
		});
	});
});
