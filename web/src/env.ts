import { defineEnvVars } from '@sveltejs/kit/env';

const optional = (value: string | undefined) => (value ? value : undefined);

export const variables = defineEnvVars({
	GAMES_FEED_URL: {
		public: true,
		static: true,
		description: 'Absolute URL of the games feed, read at build time',
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('GAMES_FEED_URL must be an absolute URL');
			return value;
		}
	},
	STANDINGS_FEED_URL: {
		public: true,
		static: true,
		description: 'Absolute URL of the standings feed, read at build time',
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('STANDINGS_FEED_URL must be an absolute URL');
			return value;
		}
	},
	SEARCH_FEED_URL: {
		public: true,
		static: true,
		description: 'Absolute URL of the search feed, read at build time',
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('SEARCH_FEED_URL must be an absolute URL');
			return value;
		}
	},
	CUP_FEED_URL: {
		public: true,
		static: true,
		description: 'Absolute URL of the Cup feed, read at build time',
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('CUP_FEED_URL must be an absolute URL');
			return value;
		}
	},
	CUP_MATCHUP_FEED_URL: {
		public: true,
		static: true,
		description:
			'Absolute URL of a Cup matchup feed, with {id} where the slot id goes, read at build time',
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('CUP_MATCHUP_FEED_URL must be an absolute URL');
			if (!value.includes('{id}')) throw new Error('CUP_MATCHUP_FEED_URL must contain {id}');
			return value;
		}
	},
	PLAYOFFS_FEED_URL: {
		public: true,
		static: true,
		description: 'Absolute URL of the playoffs feed, read at build time',
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('PLAYOFFS_FEED_URL must be an absolute URL');
			return value;
		}
	},
	PLAYOFFS_FINALS_FEED_URL: {
		public: true,
		static: true,
		description: 'Absolute URL of the playoffs finals feed, read at build time',
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('PLAYOFFS_FINALS_FEED_URL must be an absolute URL');
			return value;
		}
	},
	ALL_STAR_FEED_URL: {
		public: true,
		static: true,
		description: 'Absolute URL of the All-Star feed, read at build time',
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('ALL_STAR_FEED_URL must be an absolute URL');
			return value;
		}
	},
	GAME_DETAIL_FEED_URL: {
		public: true,
		static: true,
		description:
			"Absolute URL of a game's detail feed, with {id} where the game id goes, read at build time",
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('GAME_DETAIL_FEED_URL must be an absolute URL');
			if (!value.includes('{id}')) throw new Error('GAME_DETAIL_FEED_URL must contain {id}');
			return value;
		}
	},
	TEAM_FEED_URL: {
		public: true,
		static: true,
		description:
			"Absolute URL of a team's feed, with {code} where the lowercase team code goes, read at build time",
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('TEAM_FEED_URL must be an absolute URL');
			if (!value.includes('{code}')) throw new Error('TEAM_FEED_URL must contain {code}');
			return value;
		}
	},
	PLAYER_FEED_URL: {
		public: true,
		static: true,
		description:
			"Absolute URL of a player's feed, with {id} where the player id goes, read at build time",
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('PLAYER_FEED_URL must be an absolute URL');
			if (!value.includes('{id}')) throw new Error('PLAYER_FEED_URL must contain {id}');
			return value;
		}
	},
	CALENDAR_FEED_URL: {
		public: true,
		static: true,
		description:
			"Absolute URL of a season's calendar feed, with {season} where the season's end year or `current` goes, read at build time",
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('CALENDAR_FEED_URL must be an absolute URL');
			if (!value.includes('{season}')) throw new Error('CALENDAR_FEED_URL must contain {season}');
			return value;
		}
	},
	DAY_FEED_URL: {
		public: true,
		static: true,
		description:
			"Absolute URL of a day's feed, with {date} where the YYYY-MM-DD date goes, read at build time",
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('DAY_FEED_URL must be an absolute URL');
			if (!value.includes('{date}')) throw new Error('DAY_FEED_URL must contain {date}');
			return value;
		}
	},
	SEASON_STANDINGS_FEED_URL: {
		public: true,
		static: true,
		description:
			"Absolute URL of the standings feed of a past season, with {season} where the season's end year goes, read at build time",
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value))
				throw new Error('SEASON_STANDINGS_FEED_URL must be an absolute URL');
			if (!value.includes('{season}'))
				throw new Error('SEASON_STANDINGS_FEED_URL must contain {season}');
			return value;
		}
	},
	SEASON_TEAM_FEED_URL: {
		public: true,
		static: true,
		description:
			"Absolute URL of a team's feed in a past season, with {season} where the season's end year goes and {code} where the lowercase team code goes, read at build time",
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('SEASON_TEAM_FEED_URL must be an absolute URL');
			if (!value.includes('{season}'))
				throw new Error('SEASON_TEAM_FEED_URL must contain {season}');
			if (!value.includes('{code}')) throw new Error('SEASON_TEAM_FEED_URL must contain {code}');
			return value;
		}
	},
	SEASON_PLAYER_FEED_URL: {
		public: true,
		static: true,
		description:
			"Absolute URL of a player's feed in a past season, with {season} where the season's end year goes and {id} where the player id goes, read at build time",
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('SEASON_PLAYER_FEED_URL must be an absolute URL');
			if (!value.includes('{season}'))
				throw new Error('SEASON_PLAYER_FEED_URL must contain {season}');
			if (!value.includes('{id}')) throw new Error('SEASON_PLAYER_FEED_URL must contain {id}');
			return value;
		}
	},
	SEASON_CUP_FEED_URL: {
		public: true,
		static: true,
		description:
			"Absolute URL of the Cup feed of a past season, with {season} where the season's end year goes, read at build time",
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('SEASON_CUP_FEED_URL must be an absolute URL');
			if (!value.includes('{season}')) throw new Error('SEASON_CUP_FEED_URL must contain {season}');
			return value;
		}
	},
	SEASON_CUP_MATCHUP_FEED_URL: {
		public: true,
		static: true,
		description:
			"Absolute URL of a Cup matchup feed in a past season, with {season} where the season's end year goes and {slot} where the bracket slot id goes, read at build time",
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value))
				throw new Error('SEASON_CUP_MATCHUP_FEED_URL must be an absolute URL');
			if (!value.includes('{season}'))
				throw new Error('SEASON_CUP_MATCHUP_FEED_URL must contain {season}');
			if (!value.includes('{slot}'))
				throw new Error('SEASON_CUP_MATCHUP_FEED_URL must contain {slot}');
			return value;
		}
	},
	SEASON_PLAYOFFS_FEED_URL: {
		public: true,
		static: true,
		description:
			"Absolute URL of the playoffs feed of a past season, with {season} where the season's end year goes, read at build time",
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('SEASON_PLAYOFFS_FEED_URL must be an absolute URL');
			if (!value.includes('{season}'))
				throw new Error('SEASON_PLAYOFFS_FEED_URL must contain {season}');
			return value;
		}
	},
	SEASON_PLAYOFFS_FINALS_FEED_URL: {
		public: true,
		static: true,
		description:
			"Absolute URL of the playoffs finals feed of a past season, with {season} where the season's end year goes, read at build time",
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value))
				throw new Error('SEASON_PLAYOFFS_FINALS_FEED_URL must be an absolute URL');
			if (!value.includes('{season}'))
				throw new Error('SEASON_PLAYOFFS_FINALS_FEED_URL must contain {season}');
			return value;
		}
	},
	SEASON_ALL_STAR_FEED_URL: {
		public: true,
		static: true,
		description:
			"Absolute URL of the All-Star feed of a past season, with {season} where the season's end year goes, read at build time",
		schema: (value) => {
			if (!value) return undefined;
			if (!URL.canParse(value)) throw new Error('SEASON_ALL_STAR_FEED_URL must be an absolute URL');
			if (!value.includes('{season}'))
				throw new Error('SEASON_ALL_STAR_FEED_URL must contain {season}');
			return value;
		}
	},
	VIDEO_PLATFORM_NAME: {
		public: true,
		static: true,
		description: 'Name of the video platform shown next to the highlights',
		schema: optional
	}
});
