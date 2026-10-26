// web/tests/lib/feed/home-props.test.ts
//
// Tests for the props layer that turns the home feed into the hero of a day with no games.
//
// Tested:
// - The scenario tag and paragraph of each of the four scenarios, in English and in Spanish
// - The date of the games feed's today, in both languages, with or without the home feed
// - The next tip-off with its day and ET time; null with no next game; the network only when set
// - Coming up: null when the feed's is null; items in feed order; a single day and a range; the status labels
// - The link target of each of the nine keys
// - A null feed gives the date only
//
// What is covered:
// - Pure logic on an invented feed (tests/lib/feed/fixtures/home.json); no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/home-props.test.ts
//
// SEE: web/src/lib/feed/home-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ComingUpKey, HomeFeed, HomeScenario } from '../../../src/lib/contract/home';
import { toNoGamesView } from '../../../src/lib/feed/home-props';
import { preferLanguages } from '../../prefer-languages';

const feed = (): HomeFeed =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', 'home.json'), 'utf8')) as HomeFeed;
const TODAY = '2026-10-04';

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toNoGamesView', () => {
	it('gives the tag and paragraph of each scenario in English', () => {
		const expected: Record<HomeScenario, [string, string]> = {
			offDay: ['Off day', 'A rest day across the league. The schedule below shows the next games.'],
			allStarBreak: ['All-Star break', 'The regular season pauses for the All-Star break.'],
			finalsPreview: ['Finals preview', 'The conference finals are over. The Finals are next.'],
			offseason: [
				'Offseason',
				'The season is over. The next one starts with the preseason and Opening Night.'
			]
		};
		for (const [scenario, [tag, paragraph]] of Object.entries(expected)) {
			const source = { ...feed(), scenario: scenario as HomeScenario };
			expect(toNoGamesView(TODAY, source)).toMatchObject({ tag, paragraph });
		}
	});

	it('gives the tag and paragraph of each scenario in Spanish', () => {
		preferLanguages(['es']);
		const tags = {
			offDay: 'Día sin partidos',
			allStarBreak: 'Pausa del All-Star',
			finalsPreview: 'Previa de las Finales',
			offseason: 'Fuera de temporada'
		};
		for (const [scenario, tag] of Object.entries(tags)) {
			const view = toNoGamesView(TODAY, { ...feed(), scenario: scenario as HomeScenario });
			expect(view.tag).toBe(tag);
			expect(view.paragraph).toBeTruthy();
		}
	});

	it("formats the games feed's today in both languages", () => {
		expect(toNoGamesView(TODAY, feed()).date).toBe('Sunday, October 4');
		preferLanguages(['es']);
		expect(toNoGamesView(TODAY, feed()).date).toBe('domingo, 4 de octubre');
	});

	it('gives the next tip-off with the day and the ET time, and the network', () => {
		const view = toNoGamesView(TODAY, feed());
		expect(view.nextTipOff).toBe('Next tip-off: Tue, Oct 6 · 7:00 PM ET');
		expect(view.broadcast).toBe('Courtside TV');
	});

	it('gives no network when the next game has none', () => {
		const source = feed();
		source.nextGame!.broadcast = null;
		const view = toNoGamesView(TODAY, source);
		expect(view.broadcast).toBeNull();
		expect(view.nextTipOff).not.toBeNull();
	});

	it('gives no next tip-off and no network with no next game', () => {
		const view = toNoGamesView(TODAY, { ...feed(), nextGame: null });
		expect(view.nextTipOff).toBeNull();
		expect(view.broadcast).toBeNull();
	});

	it('gives null Coming up when the feed has none', () => {
		expect(toNoGamesView(TODAY, { ...feed(), comingUp: null }).comingUp).toBeNull();
	});

	it('maps the Coming up items in feed order with dates, ranges and status labels', () => {
		const items = toNoGamesView(TODAY, feed()).comingUp!;
		expect(items.map((i) => i.key)).toEqual([
			'openingNight',
			'cupGroupStage',
			'allStar',
			'playoffs'
		]);
		expect(items[0]).toMatchObject({
			date: 'Oct 4',
			title: 'Opening Night',
			sub: 'The regular season begins',
			status: 'done',
			statusLabel: 'Done',
			target: null
		});
		expect(items[1]).toMatchObject({
			date: 'Nov 4 – Dec 3',
			title: 'Cup group play',
			status: 'now',
			statusLabel: 'Now',
			target: 'cup'
		});
		expect(items[2]).toMatchObject({ statusLabel: 'Upcoming', target: 'allStar' });
	});

	it('maps Coming up in Spanish', () => {
		preferLanguages(['es']);
		const items = toNoGamesView(TODAY, feed()).comingUp!;
		expect(items[0]).toMatchObject({ title: 'Noche inaugural', statusLabel: 'Terminado' });
	});

	it('gives the link target of each of the nine keys', () => {
		const keys: Record<ComingUpKey, string | null> = {
			openingNight: null,
			preseason: null,
			cupGroupStage: 'cup',
			cupKnockout: 'cup',
			cupFinal: 'cup',
			allStar: 'allStar',
			playIn: 'playoffs',
			playoffs: 'playoffs',
			finals: 'playoffs'
		};
		for (const [key, target] of Object.entries(keys)) {
			const source = feed();
			source.comingUp = [
				{ key: key as ComingUpKey, startDate: '2026-11-04', endDate: null, status: 'upcoming' }
			];
			const view = toNoGamesView(TODAY, source);
			expect(view.comingUp![0].target).toBe(target);
			expect(view.comingUp![0].title).toBeTruthy();
			expect(view.comingUp![0].sub).toBeTruthy();
		}
	});

	it('gives the date only without the home feed', () => {
		expect(toNoGamesView(TODAY, null)).toEqual({
			date: 'Sunday, October 4',
			tag: null,
			paragraph: null,
			nextTipOff: null,
			broadcast: null,
			comingUp: null
		});
	});
});
