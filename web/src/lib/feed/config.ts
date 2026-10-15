import {
	ALL_STAR_FEED_URL,
	CALENDAR_FEED_URL,
	CUP_FEED_URL,
	CUP_MATCHUP_FEED_URL,
	DAY_FEED_URL,
	GAME_DETAIL_FEED_URL,
	GAMES_FEED_URL,
	PLAYER_FEED_URL,
	PLAYOFFS_FEED_URL,
	PLAYOFFS_FINALS_FEED_URL,
	SEARCH_FEED_URL,
	SEASON_PLAYER_FEED_URL,
	SEASON_STANDINGS_FEED_URL,
	SEASON_TEAM_FEED_URL,
	STANDINGS_FEED_URL,
	TEAM_FEED_URL,
	VIDEO_PLATFORM_NAME
} from '$app/env/public';

// Build-time settings, declared in src/env.ts. Re-exported here so tests mock one local module.
export const gamesFeedUrl: string | undefined = GAMES_FEED_URL;
export const standingsFeedUrl: string | undefined = STANDINGS_FEED_URL;
export const searchFeedUrl: string | undefined = SEARCH_FEED_URL;
export const cupFeedUrl: string | undefined = CUP_FEED_URL;
export const cupMatchupFeedUrl: string | undefined = CUP_MATCHUP_FEED_URL;
export const playoffsFeedUrl: string | undefined = PLAYOFFS_FEED_URL;
export const playoffsFinalsFeedUrl: string | undefined = PLAYOFFS_FINALS_FEED_URL;
export const allStarFeedUrl: string | undefined = ALL_STAR_FEED_URL;
export const gameDetailFeedUrl: string | undefined = GAME_DETAIL_FEED_URL;
export const teamFeedUrl: string | undefined = TEAM_FEED_URL;
export const playerFeedUrl: string | undefined = PLAYER_FEED_URL;
export const calendarFeedUrl: string | undefined = CALENDAR_FEED_URL;
export const dayFeedUrl: string | undefined = DAY_FEED_URL;
export const seasonStandingsFeedUrl: string | undefined = SEASON_STANDINGS_FEED_URL;
export const seasonTeamFeedUrl: string | undefined = SEASON_TEAM_FEED_URL;
export const seasonPlayerFeedUrl: string | undefined = SEASON_PLAYER_FEED_URL;
export const videoPlatformName: string | undefined = VIDEO_PLATFORM_NAME;
