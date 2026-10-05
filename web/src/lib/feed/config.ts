import { GAMES_FEED_URL, VIDEO_PLATFORM_NAME } from '$app/env/public';

// Build-time settings, declared in src/env.ts. Re-exported here so tests mock one local module.
export const gamesFeedUrl: string | undefined = GAMES_FEED_URL;
export const videoPlatformName: string | undefined = VIDEO_PLATFORM_NAME;
