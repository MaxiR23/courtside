// web/tests/lib/playoffs/layout.test.ts
//
// Tests for the playoffs bracket and Finals MVP breakpoint helpers.
//
// Tested:
// - The map without matchMedia, at 1180px and wider; the tree below
// - The breakpoint constant matches the --playoffs-bracket-break token
// - The Finals MVP section: two columns without matchMedia, at 900px and wider; one below
// - MVP_BREAKPOINT_PX matches the --playoffs-mvp-break token
//
// What is covered:
// - Happy path, missing matchMedia and the token cross-check
//
// Run with: cd web && pnpm exec vitest run tests/lib/playoffs/layout.test.ts
//
// SEE: web/src/lib/playoffs/layout.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
	BRACKET_BREAKPOINT_PX,
	BRACKET_WIDE_QUERY,
	MVP_BREAKPOINT_PX,
	MVP_WIDE_QUERY,
	bracketWideViewport,
	mvpWideViewport
} from '../../../src/lib/playoffs/layout';

function viewport(wide: boolean, wideQuery: string = BRACKET_WIDE_QUERY) {
	vi.stubGlobal('matchMedia', (query: string) => ({
		matches: query === wideQuery && wide,
		addEventListener: () => {},
		removeEventListener: () => {}
	}));
}

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('bracketWideViewport', () => {
	it('uses the map when matchMedia is unavailable', () => {
		vi.stubGlobal('matchMedia', undefined);
		expect(bracketWideViewport().current).toBe(true);
	});

	it('uses the map when the viewport is 1180px or wider', () => {
		viewport(true);
		expect(bracketWideViewport().current).toBe(true);
	});

	it('uses the tree below 1180px', () => {
		viewport(false);
		expect(bracketWideViewport().current).toBe(false);
	});

	it('matches the --playoffs-bracket-break token', () => {
		const css = readFileSync(
			join(import.meta.dirname, '../../../src/lib/styles/tokens.css'),
			'utf8'
		);
		const match = css.match(/--playoffs-bracket-break:\s*(\d+)px;/);
		expect(Number(match?.[1])).toBe(BRACKET_BREAKPOINT_PX);
	});
});

describe('mvpWideViewport', () => {
	it('uses two columns when matchMedia is unavailable', () => {
		vi.stubGlobal('matchMedia', undefined);
		expect(mvpWideViewport().current).toBe(true);
	});

	it('uses two columns when the viewport is 900px or wider', () => {
		viewport(true, MVP_WIDE_QUERY);
		expect(mvpWideViewport().current).toBe(true);
	});

	it('uses one column below 900px', () => {
		viewport(false, MVP_WIDE_QUERY);
		expect(mvpWideViewport().current).toBe(false);
	});

	it('matches the --playoffs-mvp-break token', () => {
		const css = readFileSync(
			join(import.meta.dirname, '../../../src/lib/styles/tokens.css'),
			'utf8'
		);
		const match = css.match(/--playoffs-mvp-break:\s*(\d+)px;/);
		expect(Number(match?.[1])).toBe(MVP_BREAKPOINT_PX);
	});
});
