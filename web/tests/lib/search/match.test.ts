// web/tests/lib/search/match.test.ts
//
// Tests for the search overlay's matching, ranking and cap.
//
// Tested:
// - Case and diacritics are ignored; every token must prefix a word
// - Names split on space, hyphen, period and apostrophe; teams match by city, name and code
// - A player matches by his team's words
// - Player order: exact word 4, own prefix 3, team word 1, then photo, then name A to Z
// - An empty query finds nothing
// - capPlayers caps, reports the hidden count and lifts the cap
//
// What is covered:
// - Pure logic on small feeds built in the test; no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/search/match.test.ts
//
// SEE: web/src/lib/search/match.ts
import { describe, expect, it } from 'vitest';

import type { SearchFeed, SearchPlayer, SearchTeam } from '../../../src/lib/contract/search';
import {
	buildSearchIndex,
	capPlayers,
	normalize,
	PLAYER_CAP,
	searchIndex
} from '../../../src/lib/search/match';

const team = (code: string, city: string, name: string): SearchTeam => ({
	code,
	city,
	name,
	colors: { primary: null, secondary: null },
	record: '0-0',
	division: 'Northwest',
	divisionRank: 1
});

const player = (
	id: string,
	name: string,
	teamCode = 'OKC',
	photoUrl: string | null = null
): SearchPlayer => ({
	id,
	name,
	shortName: name,
	number: null,
	position: null,
	positionAbbr: null,
	photoUrl,
	injury: null,
	team: { code: teamCode, primary: null }
});

const feed = (players: SearchPlayer[]): SearchFeed =>
	({
		teams: [
			team('NYK', 'New York', 'Knicks'),
			team('OKC', 'Oklahoma City', 'Thunder'),
			team('POR', 'Portland', 'Trail Blazers')
		],
		players
	}) as unknown as SearchFeed;

const names = (players: SearchPlayer[]) => players.map((p) => p.name);

describe('normalize', () => {
	it('lowercases and removes diacritics', () => {
		expect(normalize('Nikola Jokić')).toBe('nikola jokic');
	});
});

describe('searchIndex', () => {
	const index = buildSearchIndex(
		feed([
			player('1', 'Shai Gilgeous-Alexander'),
			player('2', 'Nikola Jokić', 'NYK'),
			player('3', 'Jaren Jackson Jr.'),
			player('4', "De'Aaron Fox")
		])
	);

	it('matches regardless of case', () => {
		expect(names(searchIndex(index, 'SHAI').players)).toEqual(['Shai Gilgeous-Alexander']);
		expect(names(searchIndex(index, 'shai').players)).toEqual(['Shai Gilgeous-Alexander']);
	});

	it('matches with and without diacritics', () => {
		expect(names(searchIndex(index, 'jokic').players)).toEqual(['Nikola Jokić']);
		expect(names(searchIndex(index, 'jokić').players)).toEqual(['Nikola Jokić']);
	});

	it('requires every token to prefix a word', () => {
		expect(names(searchIndex(index, 'shai gil').players)).toEqual(['Shai Gilgeous-Alexander']);
		expect(searchIndex(index, 'shai zzz').players).toEqual([]);
	});

	it('splits names on hyphen, period and apostrophe', () => {
		expect(names(searchIndex(index, 'alexander').players)).toEqual(['Shai Gilgeous-Alexander']);
		expect(names(searchIndex(index, 'jr').players)).toEqual(['Jaren Jackson Jr.']);
		expect(names(searchIndex(index, 'aaron').players)).toEqual(["De'Aaron Fox"]);
	});

	it('matches teams by code, city, name and token by token', () => {
		const codes = (q: string) => searchIndex(index, q).teams.map((t) => t.code);
		expect(codes('okc')).toEqual(['OKC']);
		expect(codes('thunder')).toEqual(['OKC']);
		expect(codes('oklahoma city')).toEqual(['OKC']);
		expect(codes('new york')).toEqual(['NYK']);
		expect(codes('trail blazers')).toEqual(['POR']);
	});

	it('matches a player by his team words', () => {
		expect(names(searchIndex(index, 'nyk').players)).toEqual(['Nikola Jokić']);
		expect(names(searchIndex(index, 'jokic knicks').players)).toEqual(['Nikola Jokić']);
	});

	it('returns teams in the feed order', () => {
		const codes = searchIndex(index, 't').teams.map((t) => t.code);
		expect(codes).toEqual(['OKC', 'POR']);
	});

	it('ranks a name match above a team-word match', () => {
		const ranked = buildSearchIndex(
			feed([player('1', 'Aaron Thunderson', 'NYK'), player('2', 'Zed Zero', 'OKC')])
		);
		expect(names(searchIndex(ranked, 'thunder').players)).toEqual(['Aaron Thunderson', 'Zed Zero']);
	});

	it('scores an exact word above a prefix', () => {
		const ranked = buildSearchIndex(feed([player('1', 'Ann Jackson'), player('2', 'Jack Zed')]));
		expect(names(searchIndex(ranked, 'jack').players)).toEqual(['Jack Zed', 'Ann Jackson']);
	});

	it('breaks ties by photo first, then name A to Z', () => {
		const ranked = buildSearchIndex(
			feed([
				player('1', 'Cy Jones'),
				player('2', 'Bo Jones'),
				player('3', 'Zo Jones', 'OKC', 'https://cdn.example.com/3.png')
			])
		);
		expect(names(searchIndex(ranked, 'jones').players)).toEqual([
			'Zo Jones',
			'Bo Jones',
			'Cy Jones'
		]);
	});

	it('returns nothing for an empty or whitespace-only query', () => {
		expect(searchIndex(index, '')).toEqual({ teams: [], players: [] });
		expect(searchIndex(index, '   ')).toEqual({ teams: [], players: [] });
	});
});

describe('capPlayers', () => {
	const many = Array.from({ length: 10 }, (_, i) => player(String(i), `P ${i}`));

	it('mirrors the cap token', () => {
		expect(PLAYER_CAP).toEqual({ desktop: 8, mobile: 6 });
	});

	it('caps and reports the hidden count', () => {
		expect(capPlayers(many, 8, false)).toEqual({ shown: many.slice(0, 8), hidden: 2 });
		expect(capPlayers(many, 6, false).hidden).toBe(4);
	});

	it('shows everything with showAll', () => {
		expect(capPlayers(many, 8, true)).toEqual({ shown: many, hidden: 0 });
	});

	it('hides nothing at or under the cap', () => {
		expect(capPlayers(many.slice(0, 8), 8, false)).toEqual({ shown: many.slice(0, 8), hidden: 0 });
	});
});
