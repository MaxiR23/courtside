import type { GameDetailFeed } from '#lib/contract/game-detail.ts';
import type { GamesFeed } from '#lib/contract/games.ts';
import type { PlayerFeed } from '#lib/contract/player.ts';
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
	notFound = false // report a 404 as its own reason
): Promise<unknown> {
	let response: Response;
	try {
		response = await fetchFn(url, { headers: { accept: 'application/json' } });
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
