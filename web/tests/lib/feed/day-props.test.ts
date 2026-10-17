// web/tests/lib/feed/day-props.test.ts
//
// Tests for the props layer that turns the day feed into the day page props.
//
// Tested:
// - A final past game with available stats and no leaders maps to a final-without-stats card with available stats (ADR 0054) and no highlights block without a platform name
// - With a platform name the card has the highlights block with the stored clip and the search link; pending and unavailable stats keep their variants
// - The season and its label are copied; the date, title and weekday are formatted from the feed date
// - The title and weekday are in English and in Spanish for an es browser
// - A day with no game gives an empty list
// - cardDetails maps both leaders through the leader mapping and the five team stats, keeps a null value, and gives null for a missing block; withCardDetails adds the parts present to a past final card with available stats only
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
import type { GameDetailFeed } from '../../../src/lib/contract/game-detail';
import { cardDetails, toDayView, withCardDetails } from '../../../src/lib/feed/day-props';
import { preferLanguages } from '../../prefer-languages';

const feed = (): DayFeed =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', 'day.json'), 'utf8')) as DayFeed;

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toDayView', () => {
	it('maps a final past game with available stats and no leaders to a card without a stats line', () => {
		const view = toDayView(feed());
		expect(view?.games).toHaveLength(2);
		const game = view?.games[0];
		expect(game?.status).toMatchObject({ state: 'final', winner: 'home' });
		expect(game?.details).toMatchObject({
			kind: 'final-without-stats',
			statsAvailability: 'available'
		});
		expect(game?.details).not.toHaveProperty('highlights');
	});

	it('gives the highlights block when a video platform name is passed', () => {
		const view = toDayView(feed(), { videoPlatformName: 'Video platform' });
		const details = view?.games[0].details;
		expect(details).toMatchObject({
			highlights: {
				platform: 'Video platform',
				searchUrl: 'https://example.com/search?q=x'
			}
		});
		expect(details?.kind === 'final-without-stats' && details.highlights?.videos).toHaveLength(1);
		expect(
			view?.games[1].details?.kind === 'final-without-stats' &&
				view.games[1].details.highlights?.videos
		).toEqual([]);
	});

	it('keeps the pending and unavailable stats variants', () => {
		const source = feed();
		source.day.games[0].statsAvailability = 'pending';
		source.day.games[1].statsAvailability = 'unavailable';
		const view = toDayView(source);
		expect(view?.games[0].details).toMatchObject({ statsAvailability: 'pending' });
		expect(view?.games[1].details).toMatchObject({ statsAvailability: 'unavailable' });
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

describe('cardDetails and withCardDetails', () => {
	const detail = (): GameDetailFeed =>
		JSON.parse(
			readFileSync(join(__dirname, 'fixtures', 'game-detail-past.json'), 'utf8')
		) as GameDetailFeed;
	const withStats = (): GameDetailFeed => {
		const base = detail();
		const side = {
			fieldGoalPct: 0.5,
			threePointPct: null,
			freeThrowPct: 0.7,
			rebounds: 30,
			assists: 20,
			turnovers: 10,
			steals: 5,
			blocks: 4
		};
		base.teamStats = {
			away: side,
			home: { ...side, rebounds: 33 },
			leaders: {
				fieldGoalPct: null,
				threePointPct: null,
				freeThrowPct: null,
				rebounds: null,
				assists: null,
				turnovers: null,
				steals: null,
				blocks: null
			}
		};
		return base;
	};

	it('maps both leaders and keeps a null value', () => {
		const view = cardDetails(withStats());
		expect(view.leaders?.away).toMatchObject({
			firstName: 'Ada',
			lastName: 'Quill',
			points: 31,
			rebounds: 9,
			assists: null
		});
		expect(view.leaders?.home).toMatchObject({
			firstName: 'Bo',
			lastName: 'Marlowe',
			rebounds: null
		});
	});

	it('maps the five team stats and keeps a null value', () => {
		const view = cardDetails(withStats());
		expect(view.stats?.away).toEqual({
			fieldGoalPct: 0.5,
			threePointPct: null,
			rebounds: 30,
			assists: 20,
			turnovers: 10
		});
		expect(view.stats?.home.rebounds).toBe(33);
	});

	it('gives null for a missing block and keeps the other', () => {
		const feedWithoutStats = detail();
		expect(cardDetails(feedWithoutStats).stats).toBeNull();
		expect(cardDetails(feedWithoutStats).leaders).not.toBeNull();
		const feedWithoutLeaders = { ...withStats(), leaders: null };
		expect(cardDetails(feedWithoutLeaders).leaders).toBeNull();
		expect(cardDetails(feedWithoutLeaders).stats).not.toBeNull();
	});

	it('adds the parts to a past final card with available stats only', () => {
		const games = toDayView(feed())?.games ?? [];
		const card = games[0];
		const details = cardDetails(withStats());
		const merged = withCardDetails(card, details);
		expect(merged.details).toMatchObject({
			kind: 'final-without-stats',
			leaders: details.leaders,
			stats: details.stats
		});
		expect(withCardDetails(card, null)).toBe(card);
		const pending: typeof card = {
			...card,
			details: { ...(card.details as object), statsAvailability: 'pending' } as typeof card.details
		};
		expect(withCardDetails(pending, details)).toBe(pending);
		const plain: typeof card = { ...card, details: undefined };
		expect(withCardDetails(plain, details)).toBe(plain);
	});
});
