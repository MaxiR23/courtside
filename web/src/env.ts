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
	VIDEO_PLATFORM_NAME: {
		public: true,
		static: true,
		description: 'Name of the video platform shown next to the highlights',
		schema: optional
	}
});
