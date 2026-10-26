// web/tests/lib/feed/home-props.test.ts
//
// Tests for the props layer that turns the home feed into the hero of a day with no games.
//
// Tested:
// - The scenario tag and paragraph of each of the four scenarios, in English and in Spanish
// - The date of the games feed's today, in both languages, with or without the home feed
// - The next tip-off with its day and ET time; null with no next game; the network only when set
// - Coming up: null when the feed's is null; items in feed order; a single day and a range; the status labels
// - The link target of each of the nine keys
// - A null feed gives the date only
// - Last games: null cases, the five titles and the count in both languages, the seven labels with and without a game number, order, ids, loser flags, accent, team mark
// - The empty-day box: next day and count, Go to only inside the games window, the two-weeks message, null without the feed, Spanish
// - The schedule is hidden in the offseason only
//
// What is covered:
// - Pure logic on an invented feed (tests/lib/feed/fixtures/home.json); no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/home-props.test.ts
//
// SEE: web/src/lib/feed/home-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type {
	ComingUpKey,
	HomeFeed,
	HomeScenario,
	LastGameLabel,
	LastGamesTitleKey
} from '../../../src/lib/contract/home';
import {
	hidesSchedule,
	toEmptyDayView,
	toLastGamesView,
	toNoGamesView
} from '../../../src/lib/feed/home-props';
import { preferLanguages } from '../../prefer-languages';

const feed = (): HomeFeed =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', 'home.json'), 'utf8')) as HomeFeed;
const TODAY = '2026-10-04';

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toNoGamesView', () => {
	it('gives the tag and paragraph of each scenario in English', () => {
		const expected: Record<HomeScenario, [string, string]> = {
			offDay: ['Off day', 'A rest day across the league. The schedule below shows the next games.'],
			allStarBreak: ['All-Star break', 'The regular season pauses for the All-Star break.'],
			finalsPreview: ['Finals preview', 'The conference finals are over. The Finals are next.'],
			offseason: [
				'Offseason',
				'The season is over. The next one starts with the preseason and Opening Night.'
			]
		};
		for (const [scenario, [tag, paragraph]] of Object.entries(expected)) {
			const source = { ...feed(), scenario: scenario as HomeScenario };
			expect(toNoGamesView(TODAY, source)).toMatchObject({ tag, paragraph });
		}
	});

	it('gives the tag and paragraph of each scenario in Spanish', () => {
		preferLanguages(['es']);
		const tags = {
			offDay: 'Día sin partidos',
			allStarBreak: 'Pausa del All-Star',
			finalsPreview: 'Previa de las Finales',
			offseason: 'Fuera de temporada'
		};
		for (const [scenario, tag] of Object.entries(tags)) {
			const view = toNoGamesView(TODAY, { ...feed(), scenario: scenario as HomeScenario });
			expect(view.tag).toBe(tag);
			expect(view.paragraph).toBeTruthy();
		}
	});

	it("formats the games feed's today in both languages", () => {
		expect(toNoGamesView(TODAY, feed()).date).toBe('Sunday, October 4');
		preferLanguages(['es']);
		expect(toNoGamesView(TODAY, feed()).date).toBe('domingo, 4 de octubre');
	});

	it('gives the next tip-off with the day and the ET time, and the network', () => {
		const view = toNoGamesView(TODAY, feed());
		expect(view.nextTipOff).toBe('Next tip-off: Tue, Oct 6 · 7:00 PM ET');
		expect(view.broadcast).toBe('Courtside TV');
	});

	it('gives no network when the next game has none', () => {
		const source = feed();
		source.nextGame!.broadcast = null;
		const view = toNoGamesView(TODAY, source);
		expect(view.broadcast).toBeNull();
		expect(view.nextTipOff).not.toBeNull();
	});

	it('gives no next tip-off and no network with no next game', () => {
		const view = toNoGamesView(TODAY, { ...feed(), nextGame: null });
		expect(view.nextTipOff).toBeNull();
		expect(view.broadcast).toBeNull();
	});

	it('gives null Coming up when the feed has none', () => {
		expect(toNoGamesView(TODAY, { ...feed(), comingUp: null }).comingUp).toBeNull();
	});

	it('maps the Coming up items in feed order with dates, ranges and status labels', () => {
		const items = toNoGamesView(TODAY, feed()).comingUp!;
		expect(items.map((i) => i.key)).toEqual([
			'openingNight',
			'cupGroupStage',
			'allStar',
			'playoffs'
		]);
		expect(items[0]).toMatchObject({
			date: 'Oct 4',
			title: 'Opening Night',
			sub: 'The regular season begins',
			status: 'done',
			statusLabel: 'Done',
			target: null
		});
		expect(items[1]).toMatchObject({
			date: 'Nov 4 – Dec 3',
			title: 'Cup group play',
			status: 'now',
			statusLabel: 'Now',
			target: 'cup'
		});
		expect(items[2]).toMatchObject({ statusLabel: 'Upcoming', target: 'allStar' });
	});

	it('maps Coming up in Spanish', () => {
		preferLanguages(['es']);
		const items = toNoGamesView(TODAY, feed()).comingUp!;
		expect(items[0]).toMatchObject({ title: 'Noche inaugural', statusLabel: 'Terminado' });
	});

	it('gives the link target of each of the nine keys', () => {
		const keys: Record<ComingUpKey, string | null> = {
			openingNight: null,
			preseason: null,
			cupGroupStage: 'cup',
			cupKnockout: 'cup',
			cupFinal: 'cup',
			allStar: 'allStar',
			playIn: 'playoffs',
			playoffs: 'playoffs',
			finals: 'playoffs'
		};
		for (const [key, target] of Object.entries(keys)) {
			const source = feed();
			source.comingUp = [
				{ key: key as ComingUpKey, startDate: '2026-11-04', endDate: null, status: 'upcoming' }
			];
			const view = toNoGamesView(TODAY, source);
			expect(view.comingUp![0].target).toBe(target);
			expect(view.comingUp![0].title).toBeTruthy();
			expect(view.comingUp![0].sub).toBeTruthy();
		}
	});

	it('gives the date only without the home feed', () => {
		expect(toNoGamesView(TODAY, null)).toEqual({
			date: 'Sunday, October 4',
			tag: null,
			paragraph: null,
			nextTipOff: null,
			broadcast: null,
			comingUp: null
		});
	});
});

describe('toLastGamesView', () => {
	const lastWith = (key: LastGamesTitleKey, days: number | null) => {
		const source = feed();
		source.lastGames!.title = { key, days };
		return source;
	};

	it('is null for a null feed and for no last games', () => {
		expect(toLastGamesView(null)).toBeNull();
		const source = feed();
		source.lastGames = null;
		expect(toLastGamesView(source)).toBeNull();
	});

	it.each([
		['lastNight', null, 'Last night', 'Anoche'],
		['daysAgo', 3, '3 days ago', 'Hace 3 días'],
		['beforeTheBreak', null, 'Before the break', 'Antes de la pausa'],
		['conferenceFinals', null, 'Conference finals', 'Finales de conferencia'],
		['lastGamesPlayed', null, 'Last games played', 'Últimos partidos jugados']
	] as const)('titles %s in English and Spanish', (key, days, en, es) => {
		expect(toLastGamesView(lastWith(key, days))!.title).toBe(en);
		preferLanguages(['es']);
		expect(toLastGamesView(lastWith(key, days))!.title).toBe(es);
	});

	it('falls back to the last games played for days ago without days', () => {
		expect(toLastGamesView(lastWith('daysAgo', null))!.title).toBe('Last games played');
	});

	it('counts the games in both languages', () => {
		expect(toLastGamesView(feed())!.count).toBe('2 games');
		preferLanguages(['es']);
		expect(toLastGamesView(feed())!.count).toBe('2 partidos');
		const one = feed();
		one.lastGames!.games = [one.lastGames!.games[0]];
		preferLanguages(['en']);
		expect(toLastGamesView(one)!.count).toBe('1 game');
	});

	it.each([
		['final', 'Final'],
		['finalOvertime', 'Final/OT'],
		['playIn', 'Play-In'],
		['firstRound', 'First round'],
		['conferenceSemifinals', 'Conference semifinals'],
		['conferenceFinals', 'Conference finals'],
		['finals', 'Finals']
	] as const)('labels %s, with and without a game number', (label: LastGameLabel, text) => {
		const source = feed();
		source.lastGames!.games[0].label = label;
		source.lastGames!.games[0].gameNumber = null;
		expect(toLastGamesView(source)!.games[0].label).toBe(text);
		source.lastGames!.games[0].gameNumber = 3;
		expect(toLastGamesView(source)!.games[0].label).toBe(`${text} · Game 3`);
	});

	it('labels in Spanish with the game number', () => {
		preferLanguages(['es']);
		const source = feed();
		source.lastGames!.games[0].label = 'firstRound';
		source.lastGames!.games[0].gameNumber = 3;
		expect(toLastGamesView(source)!.games[0].label).toBe('Primera ronda · Partido 3');
	});

	it('keeps the feed order and the ids', () => {
		expect(toLastGamesView(feed())!.games.map((g) => g.id)).toEqual(['g-last-1', 'g-last-2']);
	});

	it('flags the loser only on the side that is not the winner', () => {
		const [first, second] = toLastGamesView(feed())!.games;
		expect([first.away.loser, first.home.loser]).toEqual([true, false]);
		expect([second.away.loser, second.home.loser]).toEqual([false, true]);
		const source = feed();
		source.lastGames!.games[0].winner = null;
		const tied = toLastGamesView(source)!.games[0];
		expect([tied.away.loser, tied.home.loser]).toEqual([false, false]);
	});

	it('maps the scores, the accent and the team of each side', () => {
		const [first, second] = toLastGamesView(feed())!.games;
		expect([first.away.score, first.home.score]).toEqual([104, 112]);
		expect(first.away.accent).toBe('#1D4E89');
		expect(second.away.accent).toBeNull();
		expect(second.home.accent).toBe('#2E7D4F');
		expect(first.home.team).toMatchObject({
			code: 'STH',
			name: 'Southerners',
			city: 'South City',
			logo: { light: 'https://example.com/sth.svg', dark: 'https://example.com/sth-dark.svg' }
		});
		expect(second.away.team.logo).toBeUndefined();
	});

	it('gives no accent when the feed has none', () => {
		const source = feed();
		source.lastGames!.games[0].accent = null;
		const side = toLastGamesView(source)!.games[0];
		expect([side.away.accent, side.home.accent]).toEqual([null, null]);
	});
});

describe('toEmptyDayView', () => {
	it('is null for a null feed', () => {
		expect(toEmptyDayView(null)).toBeNull();
	});

	it('gives the next game day, its count and the Go to inside the window', () => {
		expect(toEmptyDayView(feed())).toEqual({
			title: 'No games on this day',
			text: 'Next games: Tue, Oct 6 · 5 games',
			goTo: { date: '2026-10-06', label: 'Go to Tue, Oct 6 →' }
		});
	});

	it('gives no Go to outside the window', () => {
		const source = feed();
		source.nextGame!.inGamesWindow = false;
		expect(toEmptyDayView(source)).toMatchObject({
			text: 'Next games: Tue, Oct 6 · 5 games',
			goTo: null
		});
	});

	it('gives the two-weeks message without a next game', () => {
		const source = feed();
		source.nextGame = null;
		expect(toEmptyDayView(source)).toMatchObject({
			text: 'No games scheduled in the next two weeks.',
			goTo: null
		});
	});

	it('speaks Spanish', () => {
		preferLanguages(['es']);
		const view = toEmptyDayView(feed())!;
		expect(view.title).toBe('No hay partidos este día');
		expect(view.text).toContain('Próximos partidos:');
		expect(view.goTo!.label).toMatch(/^Ir a .* →$/);
		const source = feed();
		source.nextGame = null;
		expect(toEmptyDayView(source)!.text).toBe(
			'No hay partidos programados en las próximas dos semanas.'
		);
	});
});

describe('hidesSchedule', () => {
	it('hides the schedule in the offseason', () => {
		expect(hidesSchedule({ ...feed(), scenario: 'offseason' })).toBe(true);
	});

	it.each(['offDay', 'allStarBreak', 'finalsPreview'] as const)('keeps it in %s', (scenario) => {
		expect(hidesSchedule({ ...feed(), scenario })).toBe(false);
	});

	it('keeps it without the feed', () => {
		expect(hidesSchedule(null)).toBe(false);
	});
});
