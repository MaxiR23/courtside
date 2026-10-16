// web/tests/lib/feed/day-props.test.ts
//
// Tests for the props layer that turns the day feed into the day page props.
//
// Tested:
// - A final past game maps to a final-without-stats card with unavailable stats and no highlights
// - The season and its label are copied; the date, title and weekday are formatted from the feed date
// - The title and weekday are in English and in Spanish for an es browser
// - A day with no game gives an empty list
// - A final All-Star game without a line score (untimed, ADR 0051) gives a card without details and the day is still shown
//
// What is covered:
// - Pure logic on a recorded feed (tests/lib/feed/fixtures/day.json); no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/day-props.test.ts
//
// SEE: web/src/lib/feed/day-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { DayFeed } from '../../../src/lib/contract/days';
import { toDayView } from '../../../src/lib/feed/day-props';
import { preferLanguages } from '../../prefer-languages';

const feed = (): DayFeed =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', 'day.json'), 'utf8')) as DayFeed;

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toDayView', () => {
	it('maps a final past game to a card without stats or highlights', () => {
		const view = toDayView(feed());
		expect(view?.games).toHaveLength(2);
		const game = view?.games[0];
		expect(game?.status).toMatchObject({ state: 'final', winner: 'home' });
		expect(game?.details).toMatchObject({
			kind: 'final-without-stats',
			statsAvailability: 'unavailable'
		});
		expect(game?.details).not.toHaveProperty('highlights');
	});

	it('copies the season and its label and the feed date', () => {
		const view = toDayView(feed());
		expect(view).toMatchObject({ season: 1999, seasonLabel: '1998-99', date: '1999-02-06' });
	});

	it('formats the title and the weekday in English from the feed date', () => {
		const view = toDayView(feed());
		expect(view?.title).toBe('February 6, 1999');
		expect(view?.weekday).toBe('Saturday');
	});

	it('formats the title and the weekday in Spanish for an es browser', () => {
		preferLanguages(['es-ES']);
		const view = toDayView(feed());
		expect(view?.title).toBe('6 de febrero de 1999');
		expect(view?.weekday).toBe('sábado');
	});

	it('gives an empty list for a day with no game', () => {
		const source = feed();
		source.day.games = [];
		expect(toDayView(source)?.games).toEqual([]);
	});

	it('gives a final All-Star game without a line score a card without details and keeps the day', () => {
		const source = feed();
		source.day.games[0].lineScore = null;
		source.day.games[0].allStar = { roundLabel: 'All-Star Game', championship: false };
		const view = toDayView(source);
		expect(view?.games).toHaveLength(2);
		expect(view?.games[0].status).toMatchObject({ state: 'final' });
		expect(view?.games[0].details).toBeUndefined();
		expect(view?.games[1].details).toBeDefined();
	});
});
