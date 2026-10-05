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
	VIDEO_PLATFORM_NAME: {
		public: true,
		static: true,
		description: 'Name of the video platform shown next to the highlights',
		schema: optional
	}
});
