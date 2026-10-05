// web/tests/lib/schedule/layout.test.ts
//
// Tests for the row layout helper.
//
// Tested:
// - Desktop row without matchMedia, at 680px and wider; mobile row below
// - The card anchor id is built from the game id
// - The breakpoint constant matches the --game-row-breakpoint token
//
// What is covered:
// - Happy path, missing matchMedia and the token cross-check
//
// Run with: cd web && pnpm exec vitest run tests/lib/schedule/layout.test.ts
//
// SEE: web/src/lib/schedule/layout.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
	cardAnchor,
	GAME_ROW_BREAKPOINT_PX,
	WIDE_QUERY,
	wideViewport
} from '../../../src/lib/schedule/layout';

function viewport(wide: boolean) {
	vi.stubGlobal('matchMedia', (query: string) => ({
		matches: query === WIDE_QUERY && wide,
		addEventListener: () => {},
		removeEventListener: () => {}
	}));
}

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('wideViewport', () => {
	it('uses the desktop row when matchMedia is unavailable', () => {
		vi.stubGlobal('matchMedia', undefined);
		expect(wideViewport().current).toBe(true);
	});

	it('uses the desktop row when the viewport is 680px or wider', () => {
		viewport(true);
		expect(wideViewport().current).toBe(true);
	});

	it('uses the mobile row below 680px', () => {
		viewport(false);
		expect(wideViewport().current).toBe(false);
	});

	it('matches the --game-row-breakpoint token', () => {
		const css = readFileSync(
			join(import.meta.dirname, '../../../src/lib/styles/tokens.css'),
			'utf8'
		);
		const match = css.match(/--game-row-breakpoint:\s*(\d+)px;/);
		expect(Number(match?.[1])).toBe(GAME_ROW_BREAKPOINT_PX);
	});
});

describe('cardAnchor', () => {
	it('builds the element id of a game card', () => {
		expect(cardAnchor('0022500001')).toBe('game-0022500001');
	});
});
