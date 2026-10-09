// Local matching and ranking for the search overlay. No request per keystroke: the index is
// built once per feed and every query runs against it.
import type { SearchFeed, SearchPlayer, SearchTeam } from '#lib/contract/search.ts';

// Mirrors --search-players-cap in tokens.css (8; 6 below 680px).
export const PLAYER_CAP = { desktop: 8, mobile: 6 } as const;

export type SearchIndex = {
	teams: { team: SearchTeam; words: string[] }[];
	players: { player: SearchPlayer; words: string[]; teamWords: string[]; sortName: string }[];
};

/** Lowercase, NFD, diacritics removed. */
export function normalize(text: string): string {
	return text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
}

const split = (text: string, separator: RegExp): string[] => text.split(separator).filter(Boolean);

function teamWords(team: SearchTeam): string[] {
	const city = normalize(team.city);
	const name = normalize(team.name);
	return [normalize(team.code), city, name, ...split(city, /\s+/), ...split(name, /\s+/)];
}

/** Builds the index once per feed. */
export function buildSearchIndex(feed: SearchFeed): SearchIndex {
	const byCode = new Map<string, string[]>();
	const teams = feed.teams.map((team) => {
		const words = teamWords(team);
		byCode.set(team.code, words);
		return { team, words };
	});
	const players = feed.players.map((player) => {
		const full = normalize(player.name);
		return {
			player,
			words: [full, ...split(full, /[\s\-.'’]+/)],
			teamWords: byCode.get(player.team.code) ?? [],
			sortName: full
		};
	});
	return { teams, players };
}

const prefixes = (token: string, words: string[]): boolean =>
	words.some((w) => w.startsWith(token));

function playerScore(token: string, own: string[], team: string[]): number | null {
	if (own.includes(token)) return 4;
	if (prefixes(token, own)) return 3;
	if (prefixes(token, team)) return 1;
	return null;
}

/** Teams in the feed's order; players by score, then photo first, then name A to Z. */
export function searchIndex(
	index: SearchIndex,
	query: string
): { teams: SearchTeam[]; players: SearchPlayer[] } {
	const tokens = normalize(query).split(/\s+/).filter(Boolean);
	if (tokens.length === 0) return { teams: [], players: [] };
	const teams = index.teams
		.filter(({ words }) => tokens.every((token) => prefixes(token, words)))
		.map(({ team }) => team);
	const scored: { player: SearchPlayer; score: number; sortName: string }[] = [];
	for (const entry of index.players) {
		let score = 0;
		let matches = true;
		for (const token of tokens) {
			const tokenScore = playerScore(token, entry.words, entry.teamWords);
			if (tokenScore === null) {
				matches = false;
				break;
			}
			score += tokenScore;
		}
		if (matches) scored.push({ player: entry.player, score, sortName: entry.sortName });
	}
	scored.sort(
		(a, b) =>
			b.score - a.score ||
			Number(b.player.photoUrl !== null) - Number(a.player.photoUrl !== null) ||
			a.sortName.localeCompare(b.sortName)
	);
	return { teams, players: scored.map(({ player }) => player) };
}

/** The players to show under the cap, and how many are hidden. */
export function capPlayers(
	players: SearchPlayer[],
	cap: number,
	showAll: boolean
): { shown: SearchPlayer[]; hidden: number } {
	if (showAll || players.length <= cap) return { shown: players, hidden: 0 };
	return { shown: players.slice(0, cap), hidden: players.length - cap };
}
