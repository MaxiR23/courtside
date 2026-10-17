// web/tests/lib/feed/postseason-mark-props.test.ts
//
// Tests for the props that turn the playoffs marks of the core feeds into the tag, context line and flag of a game and the badges of a team.
//
// Tested:
// - The Play-In tag and its context line, in English and in Spanish
// - The Playoffs tag and the context line of a round 1 to 3 game, in English and in Spanish
// - The NBA Finals tag as the finals tag, with the series summary, and the Finals game without a summary
// - A Playoffs mark with no round, conference or number gives the Playoffs tag and a null context, in English and in Spanish; a Finals mark without a number or summary gives a null context; a round without a number gives the round text only; a number without a round gives the game
// - Each of the four stakes flags, and none for null stakes
// - No mark for a null mark and for a feed without the key
// - The Finals summary composed from the wins and the winner (won, led, tied), in Spanish too, never the feed's English sentence; none when a side's wins are missing; a historical side reads its season code; seriesSummary on missing wins and on a leader with no winner
// - Each title with its tone, the order of the feed kept, none for null titles and for a feed without the key
//
// What is covered:
// - Pure logic on invented values; no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/postseason-mark-props.test.ts
//
// SEE: web/src/lib/feed/postseason-mark-props.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GamePostseason, Stakes } from '../../../src/lib/contract/games';
import type { TeamTitle } from '../../../src/lib/contract/team';
import {
	postseasonMark,
	seriesSummary,
	teamTitles
} from '../../../src/lib/feed/postseason-mark-props';
import { preferLanguages } from '../../prefer-languages';

afterEach(() => {
	vi.restoreAllMocks();
});

const playIn: GamePostseason = {
	stage: 'playin',
	round: null,
	conference: 'east',
	number: null,
	summary: null,
	playIn: 'seven_eight',
	stakes: null,
	awayWins: null,
	homeWins: null,
	seriesWinner: null
};
const series: GamePostseason = {
	stage: 'playoffs',
	round: 3,
	conference: 'west',
	number: 7,
	summary: 'Series tied 3-3',
	playIn: null,
	stakes: 'game_7',
	awayWins: null,
	homeWins: null,
	seriesWinner: null
};
const finals: GamePostseason = {
	stage: 'finals',
	round: 4,
	conference: null,
	number: 5,
	summary: 'QXA LEADS 1-3 (English sentinel)',
	playIn: null,
	stakes: 'can_clinch',
	awayWins: 1,
	homeWins: 3,
	seriesWinner: null
};

const away = { code: 'QXA', name: 'Aces', city: 'Quixote', guest: false };
const home = { code: 'QXH', name: 'Hawks', city: 'Zephyr', guest: false };
const markOf = (value: GamePostseason | null | undefined) => postseasonMark(value, away, home);

describe('postseasonMark', () => {
	it('writes the Play-In tag and the conference and game as the context', () => {
		expect(markOf(playIn)).toEqual({
			tag: 'Play-In',
			finals: false,
			context: 'East · 7th vs 8th',
			stakes: null
		});
	});

	it('writes the Spanish Play-In context', () => {
		preferLanguages(['es-ES']);
		expect(markOf(playIn)?.context).toBe('Este · 7.º contra 8.º');
	});

	it('writes the Playoffs tag and the round with the conference and the game number', () => {
		expect(markOf(series)).toEqual({
			tag: 'Playoffs',
			finals: false,
			context: 'West finals · Game 7',
			stakes: 'Game 7'
		});
		expect(markOf({ ...series, round: 1, conference: 'east', number: 2 })?.context).toBe(
			'East round 1 · Game 2'
		);
		expect(markOf({ ...series, round: 2, number: 4 })?.context).toBe('West semifinals · Game 4');
	});

	it('writes the Spanish Playoffs context', () => {
		preferLanguages(['es-ES']);
		expect(markOf(series)?.context).toBe('Final del Oeste · Partido 7');
		expect(markOf({ ...series, round: 1 })?.context).toBe('Ronda 1 del Oeste · Partido 7');
		expect(markOf({ ...series, round: 2 })?.context).toBe('Semifinales del Oeste · Partido 7');
	});

	it('writes the NBA Finals tag as the finals tag with the game and the series summary', () => {
		expect(markOf(finals)).toEqual({
			tag: 'NBA Finals',
			finals: true,
			context: 'Game 5 · QXH leads series 3–1',
			stakes: 'Can clinch'
		});
	});

	it('writes the Finals context with the game alone when the series has no summary', () => {
		expect(
			markOf({ ...finals, number: 1, awayWins: null, homeWins: null, stakes: null })?.context
		).toBe('Game 1');
	});

	it('writes the Playoffs tag and no context for a mark with no round, conference or number', () => {
		const bare: GamePostseason = {
			...series,
			round: null,
			conference: null,
			number: null,
			stakes: null
		};
		expect(markOf(bare)).toEqual({
			tag: 'Playoffs',
			finals: false,
			context: null,
			stakes: null
		});
		preferLanguages(['es-ES']);
		expect(markOf(bare)).toEqual({
			tag: 'Playoffs',
			finals: false,
			context: null,
			stakes: null
		});
	});

	it('writes the game alone for a Playoffs mark with a number and no round', () => {
		const mark: GamePostseason = { ...series, round: null, conference: null, stakes: null };
		expect(markOf(mark)?.context).toBe('Game 7');
	});

	it('writes the round alone for a Playoffs mark with a round and no number', () => {
		const mark: GamePostseason = { ...series, number: null, stakes: null };
		expect(markOf(mark)?.context).toBe('West finals');
	});

	it('writes no context for a Finals mark with no number and no summary, and the summary alone with no number', () => {
		const mark: GamePostseason = {
			...finals,
			number: null,
			awayWins: null,
			homeWins: null,
			stakes: null
		};
		expect(markOf(mark)?.context).toBeNull();
		expect(
			markOf({ ...mark, summary: 'QXA LEADS 1-3 (English sentinel)', awayWins: 1, homeWins: 3 })
				?.context
		).toBe('QXH leads series 3–1');
	});

	it('writes each stakes flag, and none for null stakes', () => {
		const flags: [Stakes, string][] = [
			['game_7', 'Game 7'],
			['elimination', 'Elimination'],
			['can_clinch', 'Can clinch'],
			['clinched', 'Clinched']
		];
		for (const [stakes, text] of flags) {
			expect(markOf({ ...finals, stakes })?.stakes).toBe(text);
		}
		expect(markOf({ ...finals, stakes: null })?.stakes).toBeNull();
	});

	it('writes the Spanish tags and flags', () => {
		preferLanguages(['es-ES']);
		expect(markOf(finals)?.tag).toBe('Finales de la NBA');
		expect(markOf(finals)?.stakes).toBe('Puede ganar la serie');
		expect(markOf({ ...finals, stakes: 'clinched' })?.stakes).toBe('Serie ganada');
	});

	it('writes no mark for a null mark and for a feed without the key', () => {
		expect(markOf(null)).toBeNull();
		expect(markOf(undefined)).toBeNull();
	});

	it('composes the Finals summary from the wins and the winner and ignores the summary string', () => {
		const won: GamePostseason = {
			...finals,
			number: 7,
			awayWins: 3,
			homeWins: 4,
			seriesWinner: 'home'
		};
		expect(markOf(won)?.context).toBe('Game 7 · QXH wins series 4–3');
		expect(markOf({ ...won, seriesWinner: 'away', awayWins: 4, homeWins: 2 })?.context).toBe(
			'Game 7 · QXA wins series 4–2'
		);
		expect(markOf({ ...finals, awayWins: 2, homeWins: 2 })?.context).toBe(
			'Game 5 · Series tied 2–2'
		);
		expect(markOf({ ...finals, awayWins: 3, homeWins: 1 })?.context).toBe(
			'Game 5 · QXA leads series 3–1'
		);
	});

	it('writes the Spanish Finals summary', () => {
		preferLanguages(['es-ES']);
		const won: GamePostseason = {
			...finals,
			number: 7,
			awayWins: 3,
			homeWins: 4,
			seriesWinner: 'home'
		};
		expect(markOf(won)?.context).toBe('Partido 7 · QXH gana la serie 4–3');
		expect(markOf({ ...finals, awayWins: 2, homeWins: 2 })?.context).toBe(
			'Partido 5 · Serie empatada 2–2'
		);
		expect(markOf(finals)?.context).toBe('Partido 5 · QXH lidera la serie 3–1');
	});

	it('writes no English sentence when a side has no wins', () => {
		const none: GamePostseason = { ...finals, awayWins: null, homeWins: 3 };
		expect(markOf(none)?.context).toBe('Game 5');
		expect(markOf({ ...none, number: null })?.context).toBeNull();
	});

	it('reads the season code of a historical side', () => {
		const historical = { ...away, code: 'NOP', seasonCode: 'NO', historical: true };
		const view = postseasonMark(
			{ ...finals, awayWins: 4, homeWins: 1, seriesWinner: 'away' },
			historical,
			home
		);
		expect(view?.context).toBe('Game 5 · NO wins series 4–1');
	});
});

describe('seriesSummary', () => {
	it('gives null for missing wins even with a winner', () => {
		expect(seriesSummary({ label: 'A', wins: null }, { label: 'B', wins: 2 }, 'second')).toBeNull();
	});

	it('names the side with more wins when there is no winner', () => {
		expect(seriesSummary({ label: 'A', wins: 1 }, { label: 'B', wins: 3 }, null)).toBe(
			'B leads series 3–1'
		);
	});
});

describe('teamTitles', () => {
	const champions: TeamTitle = { kind: 'nba_champions', year: 2027, conference: null };
	const cup: TeamTitle = { kind: 'nba_cup_champions', year: 2026, conference: null };
	const east: TeamTitle = { kind: 'conference_champions', year: null, conference: 'east' };
	const west: TeamTitle = { kind: 'conference_champions', year: null, conference: 'west' };

	it('writes each title with its tone, solid only for the NBA title', () => {
		expect(teamTitles([champions])).toEqual([{ text: '2027 NBA Champions', solid: true }]);
		expect(teamTitles([cup])).toEqual([{ text: '2026 NBA Cup Champions', solid: false }]);
		expect(teamTitles([east])).toEqual([{ text: 'East Champions', solid: false }]);
		expect(teamTitles([west])).toEqual([{ text: 'West Champions', solid: false }]);
	});

	it('keeps the order of the feed', () => {
		expect(teamTitles([champions, cup, west])?.map((title) => title.text)).toEqual([
			'2027 NBA Champions',
			'2026 NBA Cup Champions',
			'West Champions'
		]);
	});

	it('writes the Spanish titles', () => {
		preferLanguages(['es-ES']);
		expect(teamTitles([champions, cup, east])?.map((title) => title.text)).toEqual([
			'Campeones de la NBA 2027',
			'Campeones de la Copa NBA 2026',
			'Campeones del Este'
		]);
	});

	it('writes no titles for null titles and for a feed without the key', () => {
		expect(teamTitles(null)).toBeNull();
		expect(teamTitles(undefined)).toBeNull();
	});
});
