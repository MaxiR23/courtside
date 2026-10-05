import type { GamesFeed } from '#lib/contract/games.ts';

export type FeedLoadReason = 'network' | 'status' | 'body';

export class FeedLoadError extends Error {
	readonly reason: FeedLoadReason;

	constructor(reason: FeedLoadReason, message: string) {
		super(message);
		this.name = 'FeedLoadError';
		this.reason = reason;
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
	let response: Response;
	try {
		response = await fetchFn(url, { headers: { accept: 'application/json' } });
	} catch {
		throw new FeedLoadError('network', 'The games feed could not be reached');
	}
	if (!response.ok) {
		throw new FeedLoadError('status', `The games feed answered ${response.status}`);
	}
	let body: unknown;
	try {
		body = await response.json();
	} catch {
		throw new FeedLoadError('body', 'The games feed is not JSON');
	}
	if (typeof body !== 'object' || body === null || !Array.isArray((body as GamesFeed).days)) {
		throw new FeedLoadError('body', 'The games feed has no days');
	}
	return body as GamesFeed;
}
