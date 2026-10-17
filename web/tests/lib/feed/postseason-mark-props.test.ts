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
import { postseasonMark, teamTitles } from '../../../src/lib/feed/postseason-mark-props';
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
	summary: 'NYK leads 3-1',
	playIn: null,
	stakes: 'can_clinch',
	awayWins: null,
	homeWins: null,
	seriesWinner: null
};

describe('postseasonMark', () => {
	it('writes the Play-In tag and the conference and game as the context', () => {
		expect(postseasonMark(playIn)).toEqual({
			tag: 'Play-In',
			finals: false,
			context: 'East · 7th vs 8th',
			stakes: null
		});
	});

	it('writes the Spanish Play-In context', () => {
		preferLanguages(['es-ES']);
		expect(postseasonMark(playIn)?.context).toBe('Este · 7.º contra 8.º');
	});

	it('writes the Playoffs tag and the round with the conference and the game number', () => {
		expect(postseasonMark(series)).toEqual({
			tag: 'Playoffs',
			finals: false,
			context: 'West finals · Game 7',
			stakes: 'Game 7'
		});
		expect(postseasonMark({ ...series, round: 1, conference: 'east', number: 2 })?.context).toBe(
			'East round 1 · Game 2'
		);
		expect(postseasonMark({ ...series, round: 2, number: 4 })?.context).toBe(
			'West semifinals · Game 4'
		);
	});

	it('writes the Spanish Playoffs context', () => {
		preferLanguages(['es-ES']);
		expect(postseasonMark(series)?.context).toBe('Final del Oeste · Partido 7');
		expect(postseasonMark({ ...series, round: 1 })?.context).toBe('Ronda 1 del Oeste · Partido 7');
		expect(postseasonMark({ ...series, round: 2 })?.context).toBe(
			'Semifinales del Oeste · Partido 7'
		);
	});

	it('writes the NBA Finals tag as the finals tag with the game and the series summary', () => {
		expect(postseasonMark(finals)).toEqual({
			tag: 'NBA Finals',
			finals: true,
			context: 'Game 5 · NYK leads 3-1',
			stakes: 'Can clinch'
		});
	});

	it('writes the Finals context with the game alone when the series has no summary', () => {
		expect(postseasonMark({ ...finals, number: 1, summary: null, stakes: null })?.context).toBe(
			'Game 1'
		);
	});

	it('writes the Playoffs tag and no context for a mark with no round, conference or number', () => {
		const bare: GamePostseason = {
			...series,
			round: null,
			conference: null,
			number: null,
			stakes: null
		};
		expect(postseasonMark(bare)).toEqual({
			tag: 'Playoffs',
			finals: false,
			context: null,
			stakes: null
		});
		preferLanguages(['es-ES']);
		expect(postseasonMark(bare)).toEqual({
			tag: 'Playoffs',
			finals: false,
			context: null,
			stakes: null
		});
	});

	it('writes the game alone for a Playoffs mark with a number and no round', () => {
		const mark: GamePostseason = { ...series, round: null, conference: null, stakes: null };
		expect(postseasonMark(mark)?.context).toBe('Game 7');
	});

	it('writes the round alone for a Playoffs mark with a round and no number', () => {
		const mark: GamePostseason = { ...series, number: null, stakes: null };
		expect(postseasonMark(mark)?.context).toBe('West finals');
	});

	it('writes no context for a Finals mark with no number and no summary, and the summary alone with no number', () => {
		const mark: GamePostseason = { ...finals, number: null, summary: null, stakes: null };
		expect(postseasonMark(mark)?.context).toBeNull();
		expect(postseasonMark({ ...mark, summary: 'NYK leads 3-1' })?.context).toBe('NYK leads 3-1');
	});

	it('writes each stakes flag, and none for null stakes', () => {
		const flags: [Stakes, string][] = [
			['game_7', 'Game 7'],
			['elimination', 'Elimination'],
			['can_clinch', 'Can clinch'],
			['clinched', 'Clinched']
		];
		for (const [stakes, text] of flags) {
			expect(postseasonMark({ ...finals, stakes })?.stakes).toBe(text);
		}
		expect(postseasonMark({ ...finals, stakes: null })?.stakes).toBeNull();
	});

	it('writes the Spanish tags and flags', () => {
		preferLanguages(['es-ES']);
		expect(postseasonMark(finals)?.tag).toBe('Finales de la NBA');
		expect(postseasonMark(finals)?.stakes).toBe('Puede ganar la serie');
		expect(postseasonMark({ ...finals, stakes: 'clinched' })?.stakes).toBe('Serie ganada');
	});

	it('writes no mark for a null mark and for a feed without the key', () => {
		expect(postseasonMark(null)).toBeNull();
		expect(postseasonMark(undefined)).toBeNull();
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
