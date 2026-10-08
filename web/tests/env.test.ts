// web/tests/env.test.ts
//
// Tests for the build-time settings declared in src/env.ts.
//
// Tested:
// - TEAM_FEED_URL: accepts an absolute URL with {code}; empty or missing is undefined
// - TEAM_FEED_URL: rejects a relative URL and an absolute URL without {code}
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

const validate = (value: string | undefined): Outcome =>
	(variables.TEAM_FEED_URL.schema as unknown as Validator)['~standard'].validate(value);

describe('TEAM_FEED_URL', () => {
	it('accepts an absolute URL containing {code} and returns it', () => {
		const url = 'https://feeds.example.com/teams/{code}.json';
		expect(validate(url)).toEqual({ value: url });
	});

	it('returns undefined for an empty or missing value', () => {
		expect(validate('')).toEqual({ value: undefined });
		expect(validate(undefined)).toEqual({ value: undefined });
	});

	it('rejects a relative URL', () => {
		expect(validate('/teams/{code}.json')).toEqual({
			issues: [{ message: 'TEAM_FEED_URL must be an absolute URL' }]
		});
	});

	it('rejects an absolute URL without {code}', () => {
		expect(validate('https://feeds.example.com/teams.json')).toEqual({
			issues: [{ message: 'TEAM_FEED_URL must contain {code}' }]
		});
	});
});
