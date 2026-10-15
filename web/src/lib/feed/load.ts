import type { AllStarFeed } from '#lib/contract/all-star.ts';
import type { GameDetailFeed } from '#lib/contract/game-detail.ts';
import type { CalendarFeed } from '#lib/contract/calendar.ts';
import type { DayFeed } from '#lib/contract/days.ts';
import type { CupFeed } from '#lib/contract/cup.ts';
import type { CupMatchupFeed } from '#lib/contract/cup-matchup.ts';
import type { GamesFeed } from '#lib/contract/games.ts';
import type { PlayerFeed } from '#lib/contract/player.ts';
import type { PlayoffsFeed } from '#lib/contract/playoffs.ts';
import type { PlayoffsFinalsFeed } from '#lib/contract/playoffs-finals.ts';
import type { SearchFeed } from '#lib/contract/search.ts';
import type { StandingsFeed } from '#lib/contract/standings.ts';
import type { TeamFeed } from '#lib/contract/team.ts';

export type FeedLoadReason = 'network' | 'status' | 'not-found' | 'body';

const GAMES_LABEL = 'The games feed';

export class FeedLoadError extends Error {
	readonly reason: FeedLoadReason;

	constructor(reason: FeedLoadReason, message: string) {
		super(message);
		this.name = 'FeedLoadError';
		this.reason = reason;
	}
}

async function fetchFeedBody(
	url: string,
	label: string,
	fetchFn: typeof fetch,
	notFound = false, // report a 404 as its own reason
	init: Pick<RequestInit, 'cache'> = {}
): Promise<unknown> {
	let response: Response;
	try {
		response = await fetchFn(url, { ...init, headers: { accept: 'application/json' } });
	} catch {
		throw new FeedLoadError('network', `${label} could not be reached`);
	}
	if (notFound && response.status === 404) {
		throw new FeedLoadError('not-found', `${label} answered 404`);
	}
	if (!response.ok) {
		throw new FeedLoadError('status', `${label} answered ${response.status}`);
	}
	try {
		return await response.json();
	} catch {
		throw new FeedLoadError('body', `${label} is not JSON`);
	}
}

/**
 * Fetches the games feed. The API validates every feed before publishing it, so the body is
 * only checked for its shape: an object with a `days` array.
 */
export async function loadGamesFeed(
	url: string,
	fetchFn: typeof fetch = fetch
): Promise<GamesFeed> {
	const body = await fetchFeedBody(url, GAMES_LABEL, fetchFn);
	if (typeof body !== 'object' || body === null || !Array.isArray((body as GamesFeed).days)) {
		throw new FeedLoadError('body', 'The games feed has no days');
	}
	return body as GamesFeed;
}

/** The URL of one game's detail feed: the template with the encoded id in place of {id}. */
export function gameFeedUrl(template: string, id: string): string {
	return template.replaceAll('{id}', encodeURIComponent(id));
}

/**
 * Fetches a game's detail feed. A 404 is its own reason: the game does not exist. The body is
 * only checked for its shape: an object with a string `id`.
 */
export async function loadGameDetailFeed(
	url: string,
	fetchFn: typeof fetch = fetch
): Promise<GameDetailFeed> {
	const body = await fetchFeedBody(url, 'The game detail feed', fetchFn, true);
	if (
		typeof body !== 'object' ||
		body === null ||
		typeof (body as GameDetailFeed).id !== 'string'
	) {
		throw new FeedLoadError('body', 'The game detail feed has no id');
	}
	return body as GameDetailFeed;
}

/** The URL of one team's feed: the template with the encoded code in place of {code}. */
export function teamFeedUrl(template: string, code: string): string {
	return template.replaceAll('{code}', encodeURIComponent(code));
}

/**
 * Fetches a team's feed. A 404 is its own reason: the code is not a team. The body is only
 * checked for its shape: an object with a string `code`.
 */
export async function loadTeamFeed(url: string, fetchFn: typeof fetch = fetch): Promise<TeamFeed> {
	const body = await fetchFeedBody(url, 'The team feed', fetchFn, true);
	if (typeof body !== 'object' || body === null || typeof (body as TeamFeed).code !== 'string') {
		throw new FeedLoadError('body', 'The team feed has no code');
	}
	return body as TeamFeed;
}

/** The URL of one player's feed: the template with the encoded id in place of {id}. */
export function playerFeedUrl(template: string, id: string): string {
	return template.replaceAll('{id}', encodeURIComponent(id));
}

/**
 * Fetches a player's feed. A 404 is its own reason: the id is not a player. The body is only
 * checked for its shape: an object with a string `id`.
 */
export async function loadPlayerFeed(
	url: string,
	fetchFn: typeof fetch = fetch
): Promise<PlayerFeed> {
	const body = await fetchFeedBody(url, 'The player feed', fetchFn, true);
	if (typeof body !== 'object' || body === null || typeof (body as PlayerFeed).id !== 'string') {
		throw new FeedLoadError('body', 'The player feed has no id');
	}
	return body as PlayerFeed;
}

/**
 * Fetches the standings feed. The body is only checked for its shape: an object with a
 * `conferences` array.
 */
export async function loadStandingsFeed(
	url: string,
	fetchFn: typeof fetch = fetch
): Promise<StandingsFeed> {
	const body = await fetchFeedBody(url, 'The standings feed', fetchFn);
	if (
		typeof body !== 'object' ||
		body === null ||
		!Array.isArray((body as StandingsFeed).conferences)
	) {
		throw new FeedLoadError('body', 'The standings feed has no conferences');
	}
	return body as StandingsFeed;
}

/**
 * Fetches the Cup feed. The body is only checked for its shape: an object with `stages` and
 * `groups` arrays.
 */
export async function loadCupFeed(url: string, fetchFn: typeof fetch = fetch): Promise<CupFeed> {
	const body = await fetchFeedBody(url, 'The Cup feed', fetchFn);
	if (
		typeof body !== 'object' ||
		body === null ||
		!Array.isArray((body as CupFeed).stages) ||
		!Array.isArray((body as CupFeed).groups)
	) {
		throw new FeedLoadError('body', 'The Cup feed has no stages or groups');
	}
	return body as CupFeed;
}

/**
 * Fetches the playoffs feed. The body is only checked for its shape: an object with `stages`
 * and `bracket` arrays.
 */
export async function loadPlayoffsFeed(
	url: string,
	fetchFn: typeof fetch = fetch
): Promise<PlayoffsFeed> {
	const body = await fetchFeedBody(url, 'The playoffs feed', fetchFn);
	if (
		typeof body !== 'object' ||
		body === null ||
		!Array.isArray((body as PlayoffsFeed).stages) ||
		!Array.isArray((body as PlayoffsFeed).bracket)
	) {
		throw new FeedLoadError('body', 'The playoffs feed has no stages or bracket');
	}
	return body as PlayoffsFeed;
}

/**
 * Fetches the playoffs finals feed. A 404 is its own reason: no Finals game exists yet. The
 * body is only checked for its shape: an object with `games` and `road` arrays.
 */
export async function loadPlayoffsFinalsFeed(
	url: string,
	fetchFn: typeof fetch = fetch
): Promise<PlayoffsFinalsFeed> {
	const body = await fetchFeedBody(url, 'The playoffs finals feed', fetchFn, true);
	if (
		typeof body !== 'object' ||
		body === null ||
		!Array.isArray((body as PlayoffsFinalsFeed).games) ||
		!Array.isArray((body as PlayoffsFinalsFeed).road)
	) {
		throw new FeedLoadError('body', 'The playoffs finals feed has no games or road');
	}
	return body as PlayoffsFinalsFeed;
}

/**
 * Fetches the All-Star feed. The route answers 503 when it is not ready, never 404. The body is
 * only checked for its shape: an object with a string `state` and an `edition` with a `games`
 * array.
 */
export async function loadAllStarFeed(
	url: string,
	fetchFn: typeof fetch = fetch
): Promise<AllStarFeed> {
	const body = await fetchFeedBody(url, 'The All-Star feed', fetchFn);
	const feed = body as AllStarFeed | null;
	if (
		typeof body !== 'object' ||
		feed === null ||
		typeof feed.state !== 'string' ||
		typeof feed.edition !== 'object' ||
		feed.edition === null ||
		!Array.isArray(feed.edition.games)
	) {
		throw new FeedLoadError('body', 'The All-Star feed has no state or edition');
	}
	return feed;
}

/** The URL of one Cup matchup feed: the template with the encoded slot id in place of {id}. */
export function cupMatchupFeedUrl(template: string, id: string): string {
	return template.replaceAll('{id}', encodeURIComponent(id));
}

/**
 * Fetches a Cup matchup feed. A 404 is its own reason: the id is not a slot. The body is only
 * checked for its shape: an object with a string `id` and the `top` and `bottom` sides.
 * `no-cache` makes the browser revalidate with the stored ETag on every request, as for the
 * search feed.
 */
export async function loadCupMatchupFeed(
	url: string,
	fetchFn: typeof fetch = fetch
): Promise<CupMatchupFeed> {
	const body = await fetchFeedBody(url, 'The Cup matchup feed', fetchFn, true, {
		cache: 'no-cache'
	});
	const feed = body as Partial<CupMatchupFeed> | null;
	if (
		typeof body !== 'object' ||
		feed === null ||
		typeof feed.id !== 'string' ||
		typeof feed.top !== 'object' ||
		feed.top === null ||
		typeof feed.bottom !== 'object' ||
		feed.bottom === null
	) {
		throw new FeedLoadError('body', 'The Cup matchup feed has no id or sides');
	}
	return body as CupMatchupFeed;
}

/**
 * Fetches the search feed. The body is only checked for its shape: an object with `teams` and
 * `players` arrays. `no-cache` makes the browser revalidate with the stored ETag on every
 * request (If-None-Match, no preflight, since the browser adds the header and not the page),
 * and hand back the cached body on a 304. The API's CORS setup would reject a hand-set header.
 */
export async function loadSearchFeed(
	url: string,
	fetchFn: typeof fetch = fetch
): Promise<SearchFeed> {
	const body = await fetchFeedBody(url, 'The search feed', fetchFn, false, { cache: 'no-cache' });
	if (
		typeof body !== 'object' ||
		body === null ||
		!Array.isArray((body as SearchFeed).teams) ||
		!Array.isArray((body as SearchFeed).players)
	) {
		throw new FeedLoadError('body', 'The search feed has no teams or players');
	}
	return body as SearchFeed;
}

/** The URL of a season's calendar feed: the template with the encoded season (end year or `current`). */
export function calendarFeedUrl(template: string, season: string): string {
	return template.replaceAll('{season}', encodeURIComponent(season));
}

/**
 * Fetches a season's calendar feed. A 404 is its own reason: the season does not exist. The body
 * is only checked for its shape: an object with `days` and `seasons` arrays.
 */
export async function loadCalendarFeed(
	url: string,
	fetchFn: typeof fetch = fetch
): Promise<CalendarFeed> {
	const body = await fetchFeedBody(url, 'The calendar feed', fetchFn, true);
	if (
		typeof body !== 'object' ||
		body === null ||
		!Array.isArray((body as CalendarFeed).days) ||
		!Array.isArray((body as CalendarFeed).seasons)
	) {
		throw new FeedLoadError('body', 'The calendar feed has no days or seasons');
	}
	return body as CalendarFeed;
}

/** The URL of a day's feed: the template with the encoded YYYY-MM-DD date in place of {date}. */
export function dayFeedUrl(template: string, date: string): string {
	return template.replaceAll('{date}', encodeURIComponent(date));
}

/**
 * Fetches a day's feed. A 404 is its own reason: the date is not a past day. The body is only
 * checked for its shape: an object whose `day` holds a `games` array.
 */
export async function loadDayFeed(url: string, fetchFn: typeof fetch = fetch): Promise<DayFeed> {
	const body = await fetchFeedBody(url, 'The day feed', fetchFn, true);
	const day = typeof body === 'object' && body !== null ? (body as DayFeed).day : undefined;
	if (typeof day !== 'object' || day === null || !Array.isArray(day.games)) {
		throw new FeedLoadError('body', 'The day feed has no games');
	}
	return body as DayFeed;
}

/** The URL of a past season's standings feed: the template with the end year in place of {season}. */
export function seasonStandingsFeedUrl(template: string, season: number): string {
	return template.replaceAll('{season}', String(season));
}

/** The URL of a team's feed in a past season: the end year and the encoded code in place of the placeholders. */
export function seasonTeamFeedUrl(template: string, season: number, code: string): string {
	return seasonStandingsFeedUrl(template, season).replaceAll('{code}', encodeURIComponent(code));
}

/** The URL of a player's feed in a past season: the end year and the encoded id in place of the placeholders. */
export function seasonPlayerFeedUrl(template: string, season: number, id: string): string {
	return seasonStandingsFeedUrl(template, season).replaceAll('{id}', encodeURIComponent(id));
}

/** The URL of a Cup matchup feed of a past season: the end year and the encoded slot id in place of the placeholders. */
export function seasonCupMatchupFeedUrl(template: string, season: number, slot: string): string {
	return seasonStandingsFeedUrl(template, season).replaceAll('{slot}', encodeURIComponent(slot));
}
