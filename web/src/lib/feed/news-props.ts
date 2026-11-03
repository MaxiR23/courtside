import type { GameDetailFeed } from '#lib/contract/game-detail.ts';
import type { NewsArticleFeed, NewsNote } from '#lib/contract/news-article.ts';
import type { SearchFeed } from '#lib/contract/search.ts';
import { nbaDate, noteDate, noteFullDate } from '#lib/format/time.ts';
import { m } from '#lib/paraglide/messages.js';
import type {
	NewsArticleView,
	NewsBlock,
	NewsCardView,
	NewsKindFilter,
	NewsTeamOption
} from '#lib/news/types.ts';

export type NewsContext = { now: Date; language: string };

/** The context of a conversion: the clock now (read in the browser, once a feed is in) and the active language. */
export function newsContext(language: string): NewsContext {
	return { now: new Date(), language };
}

/** The home block shows this many notes. */
export const HOME_NEWS_COUNT = 10;

/** A note as a card: the labels, the date and the tags are built here. */
export function toNewsCard(note: NewsNote, { now, language }: NewsContext): NewsCardView {
	return {
		id: note.id,
		kind: note.kind,
		kindLabel: note.kind === 'recap' ? m.news_kind_recap() : m.news_kind_news(),
		teamTag: note.teams[0]?.toUpperCase() ?? null,
		english: language === 'es' && note.language === 'en',
		date: noteDate(note.published, now),
		headline: note.headline,
		description: note.description,
		photo: note.photo
			? { url: note.photo.url, width: note.photo.width, height: note.photo.height }
			: null
	};
}

/**
 * A block's state from its source. `undefined` (no URL, or a season the news does not cover) and
 * every failure, a 404 included, draw nothing; so does a feed with no notes.
 */
export function newsBlock<T>(
	source: { feed: T | null; failed: boolean } | null | undefined,
	toView: (feed: T) => NewsCardView[]
): NewsBlock {
	if (source === undefined) return null;
	if (source === null || (source.feed === null && !source.failed)) return { kind: 'loading' };
	if (source.feed === null) return null;
	const notes = toView(source.feed);
	return notes.length === 0 ? null : { kind: 'ready', notes };
}

/** The first notes of a feed, for the home block. */
export function homeNews(notes: readonly NewsNote[], context: NewsContext): NewsCardView[] {
	return notes.slice(0, HOME_NEWS_COUNT).map((note) => toNewsCard(note, context));
}

/** All the notes of a feed as cards. */
export function newsCards(notes: readonly NewsNote[], context: NewsContext): NewsCardView[] {
	return notes.map((note) => toNewsCard(note, context));
}

/** The recap block of a game: the note of the article feed, nothing when it holds none. */
export function recapBlock(feed: NewsArticleFeed, context: NewsContext): NewsCardView[] {
	return feed.note ? [toNewsCard(feed.note, context)] : [];
}

/** A game's day as the NBA day (ADR 0082), from its tip-off; null until the detail feed is in. */
export function gameDayLabel(feed: GameDetailFeed | null): string | null {
	return feed ? nbaDate(feed.startTime, { day: 'numeric', month: 'short' }) : null;
}

/**
 * A note page. `gameDate` is the game's day from its detail feed: null until it loads or when it
 * fails, and the game button then shows the score alone.
 */
export function toNewsArticle(
	feed: NewsArticleFeed,
	context: NewsContext,
	gameDate: string | null
): NewsArticleView | null {
	const note = feed.note;
	if (!note) return null;
	const game = feed.game;
	let relatedGame: NewsArticleView['related']['game'] = null;
	if (game) {
		const away = game.away.code ?? game.away.name ?? '';
		const home = game.home.code ?? game.home.name ?? '';
		const label = game.score
			? m.news_related_game({
					away,
					awayScore: game.score.away,
					homeScore: game.score.home,
					home
				})
			: m.news_related_game_no_score({ away, home });
		relatedGame = {
			id: game.id,
			label: gameDate ? m.news_related_game_dated({ label, date: gameDate }) : label
		};
	}
	return {
		card: toNewsCard(note, context),
		fullDate: noteFullDate(note.published),
		credit: note.photo?.credit ?? null,
		related: {
			players: note.players.map((player) => ({ id: player.playerId, name: player.name })),
			teams: note.teams.map((code) => ({ code: code.toLowerCase(), label: code.toUpperCase() })),
			game: relatedGame
		}
	};
}

/** The cards the type filter leaves. */
export function filterByKind(notes: NewsCardView[], filter: NewsKindFilter): NewsCardView[] {
	return filter === 'all' ? notes : notes.filter((note) => note.kind === filter);
}

/** The 30 teams of the search feed for the team select, sorted in the active language. */
export function teamOptions(search: SearchFeed, language: string): NewsTeamOption[] {
	return search.teams
		.map((team) => ({ code: team.code.toLowerCase(), label: `${team.city} ${team.name}` }))
		.sort((a, b) => a.label.localeCompare(b.label, language));
}
