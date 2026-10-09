// web/tests/env.test.ts
//
// Tests for the build-time settings declared in src/env.ts.
//
// Tested:
// - TEAM_FEED_URL: accepts an absolute URL with {code}; empty or missing is undefined
// - TEAM_FEED_URL: rejects a relative URL and an absolute URL without {code}
// - PLAYER_FEED_URL: accepts an absolute URL with {id}; empty or missing is undefined
// - PLAYER_FEED_URL: rejects a relative URL and an absolute URL without {id}
// - STANDINGS_FEED_URL: accepts an absolute URL; empty or missing is undefined; rejects a relative URL
// - SEARCH_FEED_URL: accepts an absolute URL; empty or missing is undefined; rejects a relative URL
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
	name: 'TEAM_FEED_URL' | 'PLAYER_FEED_URL' | 'STANDINGS_FEED_URL' | 'SEARCH_FEED_URL',
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
