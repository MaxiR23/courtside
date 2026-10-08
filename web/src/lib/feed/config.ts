import {
	GAME_DETAIL_FEED_URL,
	GAMES_FEED_URL,
	PLAYER_FEED_URL,
	TEAM_FEED_URL,
	VIDEO_PLATFORM_NAME
} from '$app/env/public';

// Build-time settings, declared in src/env.ts. Re-exported here so tests mock one local module.
export const gamesFeedUrl: string | undefined = GAMES_FEED_URL;
export const gameDetailFeedUrl: string | undefined = GAME_DETAIL_FEED_URL;
export const teamFeedUrl: string | undefined = TEAM_FEED_URL;
export const playerFeedUrl: string | undefined = PLAYER_FEED_URL;
export const videoPlatformName: string | undefined = VIDEO_PLATFORM_NAME;
