// web/tests/env.test.ts
//
// Tests for the build-time settings declared in src/env.ts.
//
// Tested:
// - TEAM_FEED_URL: accepts an absolute URL with {code}; empty or missing is undefined
// - TEAM_FEED_URL: rejects a relative URL and an absolute URL without {code}
// - PLAYER_FEED_URL: accepts an absolute URL with {id}; empty or missing is undefined
// - PLAYER_FEED_URL: rejects a relative URL and an absolute URL without {id}
// - CUP_MATCHUP_FEED_URL: accepts an absolute URL with {id}; empty or missing is undefined
// - CUP_MATCHUP_FEED_URL: rejects a relative URL and an absolute URL without {id}
// - STANDINGS_FEED_URL: accepts an absolute URL; empty or missing is undefined; rejects a relative URL
// - SEARCH_FEED_URL: accepts an absolute URL; empty or missing is undefined; rejects a relative URL
// - CUP_FEED_URL: accepts an absolute URL; empty or missing is undefined; rejects a relative URL
// - PLAYOFFS_FEED_URL: accepts an absolute URL; empty or missing is undefined; rejects a relative URL
// - PLAYOFFS_FINALS_FEED_URL: accepts an absolute URL; empty or missing is undefined; rejects a relative URL
// - ALL_STAR_FEED_URL: accepts an absolute URL; empty or missing is undefined; rejects a relative URL
// - HOME_FEED_URL: accepts an absolute URL; empty or missing is undefined; rejects a relative URL
// - POWER_RANKING_FEED_URL: accepts an absolute URL; empty or missing is undefined; rejects a relative URL
// - CALENDAR_FEED_URL: accepts an absolute URL with {season}; empty or missing is undefined
// - CALENDAR_FEED_URL: rejects a relative URL and an absolute URL without {season}
// - DAY_FEED_URL: accepts an absolute URL with {date}; empty or missing is undefined
// - DAY_FEED_URL: rejects a relative URL and an absolute URL without {date}
// - SEASON_STANDINGS_FEED_URL, SEASON_TEAM_FEED_URL, SEASON_PLAYER_FEED_URL, SEASON_CUP_FEED_URL,
//   SEASON_CUP_MATCHUP_FEED_URL, SEASON_PLAYOFFS_FEED_URL, SEASON_PLAYOFFS_FINALS_FEED_URL,
//   SEASON_ALL_STAR_FEED_URL: accept an absolute URL with
//   their placeholders; empty or missing is undefined; reject a relative URL and a missing placeholder
//
// What is covered:
// - Happy path, edge cases (empty, missing) and error cases, on the schema alone
//
// Run with: cd web && pnpm exec vitest run tests/env.test.ts
//
// SEE: web/src/env.ts
import { describe, expect, it } from 'vitest';

import { variables } from '../src/env';

type Outcome = { value: unknown } | { issues: readonly { message: string }[] };
type Validator = { '~standard': { validate: (value: unknown) => Outcome } };

const validate = (
	name:
		| 'SEASON_STANDINGS_FEED_URL'
		| 'SEASON_TEAM_FEED_URL'
		| 'SEASON_PLAYER_FEED_URL'
		| 'SEASON_CUP_FEED_URL'
		| 'SEASON_CUP_MATCHUP_FEED_URL'
		| 'SEASON_PLAYOFFS_FEED_URL'
		| 'SEASON_PLAYOFFS_FINALS_FEED_URL'
		| 'SEASON_ALL_STAR_FEED_URL'
		| 'TEAM_FEED_URL'
		| 'PLAYER_FEED_URL'
		| 'STANDINGS_FEED_URL'
		| 'SEARCH_FEED_URL'
		| 'CUP_FEED_URL'
		| 'CUP_MATCHUP_FEED_URL'
		| 'PLAYOFFS_FEED_URL'
		| 'PLAYOFFS_FINALS_FEED_URL'
		| 'ALL_STAR_FEED_URL'
		| 'HOME_FEED_URL'
		| 'POWER_RANKING_FEED_URL'
		| 'CALENDAR_FEED_URL'
		| 'DAY_FEED_URL',
	value: string | undefined
): Outcome => (variables[name].schema as unknown as Validator)['~standard'].validate(value);

describe('TEAM_FEED_URL', () => {
	it('accepts an absolute URL containing {code} and returns it', () => {
		const url = 'https://feeds.example.com/teams/{code}.json';
		expect(validate('TEAM_FEED_URL', url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('TEAM_FEED_URL', '')).toEqual({ value: undefined });
		expect(validate('TEAM_FEED_URL', undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('TEAM_FEED_URL', '/teams/{code}.json')).toEqual({
			issues: [{ message: 'TEAM_FEED_URL must be an absolute URL' }]
		});
	});

	it('rejects an absolute URL without {code}', () => {
		expect(validate('TEAM_FEED_URL', 'https://feeds.example.com/teams.json')).toEqual({
			issues: [{ message: 'TEAM_FEED_URL must contain {code}' }]
		});
	});
});

describe('PLAYER_FEED_URL', () => {
	it('accepts an absolute URL containing {id} and returns it', () => {
		const url = 'https://feeds.example.com/players/{id}.json';
		expect(validate('PLAYER_FEED_URL', url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('PLAYER_FEED_URL', '')).toEqual({ value: undefined });
		expect(validate('PLAYER_FEED_URL', undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('PLAYER_FEED_URL', '/players/{id}.json')).toEqual({
			issues: [{ message: 'PLAYER_FEED_URL must be an absolute URL' }]
		});
	});

	it('rejects an absolute URL without {id}', () => {
		expect(validate('PLAYER_FEED_URL', 'https://feeds.example.com/players.json')).toEqual({
			issues: [{ message: 'PLAYER_FEED_URL must contain {id}' }]
		});
	});
});

describe('CUP_MATCHUP_FEED_URL', () => {
	it('accepts an absolute URL containing {id} and returns it', () => {
		const url = 'https://feeds.example.com/cup/matchups/{id}.json';
		expect(validate('CUP_MATCHUP_FEED_URL', url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('CUP_MATCHUP_FEED_URL', '')).toEqual({ value: undefined });
		expect(validate('CUP_MATCHUP_FEED_URL', undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('CUP_MATCHUP_FEED_URL', '/cup/matchups/{id}.json')).toEqual({
			issues: [{ message: 'CUP_MATCHUP_FEED_URL must be an absolute URL' }]
		});
	});

	it('rejects an absolute URL without {id}', () => {
		expect(validate('CUP_MATCHUP_FEED_URL', 'https://feeds.example.com/cup/matchups.json')).toEqual(
			{
				issues: [{ message: 'CUP_MATCHUP_FEED_URL must contain {id}' }]
			}
		);
	});
});

describe('STANDINGS_FEED_URL', () => {
	it('accepts an absolute URL and returns it', () => {
		const url = 'https://feeds.example.com/standings.json';
		expect(validate('STANDINGS_FEED_URL', url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('STANDINGS_FEED_URL', '')).toEqual({ value: undefined });
		expect(validate('STANDINGS_FEED_URL', undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('STANDINGS_FEED_URL', '/standings.json')).toEqual({
			issues: [{ message: 'STANDINGS_FEED_URL must be an absolute URL' }]
		});
	});
});

describe('SEARCH_FEED_URL', () => {
	it('accepts an absolute URL and returns it', () => {
		const url = 'https://feeds.example.com/search.json';
		expect(validate('SEARCH_FEED_URL', url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('SEARCH_FEED_URL', '')).toEqual({ value: undefined });
		expect(validate('SEARCH_FEED_URL', undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('SEARCH_FEED_URL', '/search.json')).toEqual({
			issues: [{ message: 'SEARCH_FEED_URL must be an absolute URL' }]
		});
	});
});

describe('CUP_FEED_URL', () => {
	it('accepts an absolute URL and returns it', () => {
		const url = 'https://feeds.example.com/cup.json';
		expect(validate('CUP_FEED_URL', url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('CUP_FEED_URL', '')).toEqual({ value: undefined });
		expect(validate('CUP_FEED_URL', undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('CUP_FEED_URL', '/cup.json')).toEqual({
			issues: [{ message: 'CUP_FEED_URL must be an absolute URL' }]
		});
	});
});

describe('PLAYOFFS_FEED_URL', () => {
	it('accepts an absolute URL and returns it', () => {
		const url = 'https://feeds.example.com/playoffs.json';
		expect(validate('PLAYOFFS_FEED_URL', url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('PLAYOFFS_FEED_URL', '')).toEqual({ value: undefined });
		expect(validate('PLAYOFFS_FEED_URL', undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('PLAYOFFS_FEED_URL', '/playoffs.json')).toEqual({
			issues: [{ message: 'PLAYOFFS_FEED_URL must be an absolute URL' }]
		});
	});
});

describe('PLAYOFFS_FINALS_FEED_URL', () => {
	it('accepts an absolute URL and returns it', () => {
		const url = 'https://feeds.example.com/playoffs-finals.json';
		expect(validate('PLAYOFFS_FINALS_FEED_URL', url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('PLAYOFFS_FINALS_FEED_URL', '')).toEqual({ value: undefined });
		expect(validate('PLAYOFFS_FINALS_FEED_URL', undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('PLAYOFFS_FINALS_FEED_URL', '/playoffs-finals.json')).toEqual({
			issues: [{ message: 'PLAYOFFS_FINALS_FEED_URL must be an absolute URL' }]
		});
	});
});

describe('ALL_STAR_FEED_URL', () => {
	it('accepts an absolute URL and returns it', () => {
		const url = 'https://feeds.example.com/all-star.json';
		expect(validate('ALL_STAR_FEED_URL', url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('ALL_STAR_FEED_URL', '')).toEqual({ value: undefined });
		expect(validate('ALL_STAR_FEED_URL', undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('ALL_STAR_FEED_URL', '/all-star.json')).toEqual({
			issues: [{ message: 'ALL_STAR_FEED_URL must be an absolute URL' }]
		});
	});
});

describe('HOME_FEED_URL', () => {
	it('accepts an absolute URL and returns it', () => {
		const url = 'https://feeds.example.com/home.json';
		expect(validate('HOME_FEED_URL', url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('HOME_FEED_URL', '')).toEqual({ value: undefined });
		expect(validate('HOME_FEED_URL', undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('HOME_FEED_URL', '/home.json')).toEqual({
			issues: [{ message: 'HOME_FEED_URL must be an absolute URL' }]
		});
	});
});

describe('POWER_RANKING_FEED_URL', () => {
	it('accepts an absolute URL and returns it', () => {
		const url = 'https://feeds.example.com/power-ranking.json';
		expect(validate('POWER_RANKING_FEED_URL', url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('POWER_RANKING_FEED_URL', '')).toEqual({ value: undefined });
		expect(validate('POWER_RANKING_FEED_URL', undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('POWER_RANKING_FEED_URL', '/power-ranking.json')).toEqual({
			issues: [{ message: 'POWER_RANKING_FEED_URL must be an absolute URL' }]
		});
	});
});

describe('CALENDAR_FEED_URL', () => {
	it('accepts an absolute URL containing {season} and returns it', () => {
		const url = 'https://feeds.example.com/seasons/{season}/calendar.json';
		expect(validate('CALENDAR_FEED_URL', url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('CALENDAR_FEED_URL', '')).toEqual({ value: undefined });
		expect(validate('CALENDAR_FEED_URL', undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('CALENDAR_FEED_URL', '/seasons/{season}/calendar.json')).toEqual({
			issues: [{ message: 'CALENDAR_FEED_URL must be an absolute URL' }]
		});
	});

	it('rejects an absolute URL without {season}', () => {
		expect(validate('CALENDAR_FEED_URL', 'https://feeds.example.com/feed.json')).toEqual({
			issues: [{ message: 'CALENDAR_FEED_URL must contain {season}' }]
		});
	});
});

describe('DAY_FEED_URL', () => {
	it('accepts an absolute URL containing {date} and returns it', () => {
		const url = 'https://feeds.example.com/days/{date}.json';
		expect(validate('DAY_FEED_URL', url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('DAY_FEED_URL', '')).toEqual({ value: undefined });
		expect(validate('DAY_FEED_URL', undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('DAY_FEED_URL', '/days/{date}.json')).toEqual({
			issues: [{ message: 'DAY_FEED_URL must be an absolute URL' }]
		});
	});

	it('rejects an absolute URL without {date}', () => {
		expect(validate('DAY_FEED_URL', 'https://feeds.example.com/feed.json')).toEqual({
			issues: [{ message: 'DAY_FEED_URL must contain {date}' }]
		});
	});
});

describe.each([
	{
		name: 'SEASON_STANDINGS_FEED_URL' as const,
		url: 'https://feeds.example.com/seasons/{season}/standings.json',
		extra: null
	},
	{
		name: 'SEASON_TEAM_FEED_URL' as const,
		url: 'https://feeds.example.com/seasons/{season}/teams/{code}.json',
		extra: '{code}'
	},
	{
		name: 'SEASON_PLAYER_FEED_URL' as const,
		url: 'https://feeds.example.com/seasons/{season}/players/{id}.json',
		extra: '{id}'
	},
	{
		name: 'SEASON_CUP_FEED_URL' as const,
		url: 'https://feeds.example.com/seasons/{season}/cup.json',
		extra: null
	},
	{
		name: 'SEASON_CUP_MATCHUP_FEED_URL' as const,
		url: 'https://feeds.example.com/seasons/{season}/cup/matchups/{slot}.json',
		extra: '{slot}'
	},
	{
		name: 'SEASON_PLAYOFFS_FEED_URL' as const,
		url: 'https://feeds.example.com/seasons/{season}/playoffs.json',
		extra: null
	},
	{
		name: 'SEASON_PLAYOFFS_FINALS_FEED_URL' as const,
		url: 'https://feeds.example.com/seasons/{season}/playoffs/finals.json',
		extra: null
	},
	{
		name: 'SEASON_ALL_STAR_FEED_URL' as const,
		url: 'https://feeds.example.com/seasons/{season}/all-star.json',
		extra: null
	}
])('$name', ({ name, url, extra }) => {
	it('accepts an absolute URL with its placeholders and returns it', () => {
		expect(validate(name, url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate(name, '')).toEqual({ value: undefined });
		expect(validate(name, undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate(name, '/seasons/{season}.json')).toEqual({
			issues: [{ message: `${name} must be an absolute URL` }]
		});
	});

	it('rejects an absolute URL without {season}', () => {
		expect(validate(name, 'https://feeds.example.com/seasons/2005.json')).toEqual({
			issues: [{ message: `${name} must contain {season}` }]
		});
	});

	it.runIf(extra !== null)('rejects an absolute URL without its second placeholder', () => {
		expect(validate(name, 'https://feeds.example.com/seasons/{season}/x.json')).toEqual({
			issues: [{ message: `${name} must contain ${extra}` }]
		});
	});
});
