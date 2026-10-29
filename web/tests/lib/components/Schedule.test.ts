// web/tests/lib/components/Schedule.test.ts
//
// Tests for the Schedule component.
//
// Tested:
// - Freshness label: "Recently updated" under 1 minute, the minutes from 1 minute on, whole hours from 60 minutes on, in English and Spanish
// - Header: kicker, selected day, game count, freshness; today selected by default
// - Selecting a day changes the heading, count and games; a day with no games shows the day, 0 games and the no-games message
// - Desktop row and full counts on a wide viewport; mobile row and numbers below it
// - The header takes the mobile class below 680px when it wraps, so its count and freshness label left-align; not when narrow but not wrapped, on a wide viewport or without matchMedia
// - The staggered list entrance on first view and on a day change, not on the same day
// - The list is hidden until it first scrolls into view
// - A card that cannot expand links its team names to the page given by teamHref
// - Each expandable card links to the detail page given by gameHref
// - Only one game card is open at a time; clicking an open card closes it
// - The open card can be bound from outside; each card has an anchor id; the section has the schedule anchor
// - The playing highlight stops when its card closes, another opens or the day changes
// - The empty-day box replaces the no-games row when emptyDay and windowHref are given; a day with games shows no box; without either the old row shows
// - Spoiler-free mode hides final scores until a card opens
// - Spanish copy, including the no-games message, with a Spanish browser preference
// - The kicker and the day title are drawn by SectionHead at the home size
//
// What is covered:
// - Each state, including a day with no games, plus interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/Schedule.test.ts
//
// SEE: web/src/lib/components/Schedule.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ScheduleDay, ScheduleGame } from '../../../src/lib/schedule/types';
import { preferLanguages } from '../../prefer-languages';

import Schedule from '../../../src/lib/components/Schedule.svelte';

const team = (code: string, name: string, city: string) => ({ code, name, city, guest: false });
const game = (id: string, awayScore: number): ScheduleGame => ({
	id,
	cupTag: null,
	postseasonMark: null,
	allStarMark: null,
	away: team('GSW', 'Warriors', 'Golden State'),
	home: team('LAL', 'Lakers', 'Los Angeles'),
	status: { state: 'final', awayScore, homeScore: 100, winner: 'home' }
});
const counts = [1, 0, 2, 3, 1, 1, 1];
const days: ScheduleDay[] = counts.map((n, i) => ({
	date: new Date(2026, 9, 1 + i, 12),
	games: Array.from({ length: n }, (_, k) => game(`${i}-${k}`, 90 + k))
}));
const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const props = { days, updatedMinutesAgo: 3, gameHref, teamHref };

function wideViewport(wide: boolean) {
	vi.stubGlobal('matchMedia', (query: string) => ({
		matches: query.includes('min-width') ? wide : false,
		addEventListener: () => {},
		removeEventListener: () => {}
	}));
}

// Stubs ResizeObserver and the offsets jsdom does not lay out: .heading is 60px tall at the top,
// .meta starts at 68 (below it) or at 20 (beside it).
function stubHeaderLayout(wrapped: boolean) {
	vi.stubGlobal(
		'ResizeObserver',
		class {
			observe() {}
			disconnect() {}
		}
	);
	const offsets = (el: HTMLElement) => ({
		top: el.classList.contains('meta') ? (wrapped ? 68 : 20) : 0,
		height: el.classList.contains('heading') ? 60 : 0
	});
	Object.defineProperty(HTMLElement.prototype, 'offsetTop', {
		configurable: true,
		get(this: HTMLElement) {
			return offsets(this).top;
		}
	});
	Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
		configurable: true,
		get(this: HTMLElement) {
			return offsets(this).height;
		}
	});
}

const cells = (container: HTMLElement) =>
	container.querySelectorAll<HTMLButtonElement>('button.day');

let callbacks: ((entries: { isIntersecting: boolean }[]) => void)[] = [];
let animate: ReturnType<typeof vi.fn>;

beforeEach(() => {
	callbacks = [];
	animate = vi.fn(() => ({ cancel: vi.fn() }));
	const root = document.documentElement.style;
	root.setProperty('--list-entrance-offset', '18px');
	root.setProperty('--list-entrance-duration', '600ms');
	root.setProperty('--list-entrance-stagger', '70ms');
	root.setProperty('--ease', 'linear');
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	Reflect.deleteProperty(HTMLElement.prototype, 'animate');
	Reflect.deleteProperty(HTMLElement.prototype, 'offsetTop');
	Reflect.deleteProperty(HTMLElement.prototype, 'offsetHeight');
});

function stubEntrance() {
	wideViewport(true);
	class FakeObserver {
		constructor(callback: (typeof callbacks)[number]) {
			callbacks.push(callback);
		}
		observe() {}
		disconnect() {}
	}
	vi.stubGlobal('IntersectionObserver', FakeObserver);
	Object.assign(HTMLElement.prototype, { animate });
}

describe('Schedule', () => {
	it('draws the kicker and the day title through SectionHead at the home size', () => {
		const { container } = render(Schedule, { props });
		expect(container.querySelector('.heading .titled > .kicker')?.textContent).toBe('Schedule');
		expect(container.querySelector('.heading .section-head h2')?.classList.contains('home')).toBe(
			true
		);
	});

	it('shows the SCHEDULE kicker, the selected day, the game count and the freshness label', () => {
		render(Schedule, { props });
		expect(screen.getByText('Schedule')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 2 }).textContent?.trim()).toBe('Sunday, October 4');
		expect(screen.getAllByText('3 games').length).toBeGreaterThanOrEqual(1);
		expect(screen.getByText('Updated 3m ago')).toBeTruthy();
	});

	describe('freshness label', () => {
		it.each([
			[0, 'en', 'Recently updated'],
			[0, 'es', 'Actualizado recientemente'],
			[1, 'en', 'Updated 1m ago'],
			[1, 'es', 'Actualizado hace 1m'],
			[45, 'en', 'Updated 45m ago'],
			[45, 'es', 'Actualizado hace 45m'],
			[59, 'en', 'Updated 59m ago'],
			[59, 'es', 'Actualizado hace 59m'],
			[60, 'en', 'Updated 1h ago'],
			[60, 'es', 'Actualizado hace 1h'],
			[119, 'en', 'Updated 1h ago'],
			[119, 'es', 'Actualizado hace 1h'],
			[120, 'en', 'Updated 2h ago'],
			[120, 'es', 'Actualizado hace 2h'],
			[650, 'en', 'Updated 10h ago'],
			[650, 'es', 'Actualizado hace 10h']
		])('shows the label for %i minutes in %s', (minutes, language, text) => {
			if (language === 'es') preferLanguages(['es-ES']);
			const { container } = render(Schedule, { props: { ...props, updatedMinutesAgo: minutes } });
			expect(container.querySelector('.meta .updated')?.textContent?.trim()).toBe(text);
		});

		it('does not show 0 minutes', () => {
			render(Schedule, { props: { ...props, updatedMinutesAgo: 0 } });
			expect(screen.queryByText('Updated 0m ago')).toBeNull();
		});
	});

	it('selects today by default', () => {
		const { container } = render(Schedule, { props });
		expect(cells(container)[3].getAttribute('aria-current')).toBe('true');
		expect(container.querySelectorAll('li')).toHaveLength(3);
	});

	it('changes the heading, the count and the games when another day is selected', async () => {
		const { container } = render(Schedule, { props });
		await fireEvent.click(cells(container)[2]);
		expect(screen.getByRole('heading', { level: 2 }).textContent?.trim()).toBe(
			'Saturday, October 3'
		);
		expect(container.querySelectorAll('li')).toHaveLength(2);
		expect(container.querySelector('.meta .count')?.textContent).toBe('2 games');
	});

	it('shows the day, 0 games and the no-games message instead of cards on a day with no games', () => {
		const { container } = render(Schedule, { props: { ...props, selected: 1 } });
		expect(screen.getByRole('heading', { level: 2 }).textContent?.trim()).toBe('Friday, October 2');
		expect(container.querySelector('.meta .count')?.textContent).toBe('0 games');
		const message = screen.getByText('No games scheduled for this day.');
		expect(message.closest('.blueprint-frame')).not.toBeNull();
		expect(container.querySelectorAll('li')).toHaveLength(0);
		expect(container.querySelector('ul.games')).toBeNull();
	});

	it('does not show the no-games message on a day with games', () => {
		render(Schedule, { props });
		expect(screen.queryByText('No games scheduled for this day.')).toBeNull();
	});

	it('swaps the no-games message for the game cards when a day with games is selected', async () => {
		const { container } = render(Schedule, { props: { ...props, selected: 1 } });
		expect(screen.getByText('No games scheduled for this day.')).toBeTruthy();
		await fireEvent.click(cells(container)[2]);
		expect(screen.queryByText('No games scheduled for this day.')).toBeNull();
		expect(container.querySelectorAll('li')).toHaveLength(2);
	});

	it('shows the no-games message in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		const { container } = render(Schedule, { props: { ...props, selected: 1 } });
		expect(screen.getByText('No hay partidos programados para este día.')).toBeTruthy();
		expect(container.querySelector('.meta .count')?.textContent).toBe('0 partidos');
	});

	it('has the schedule anchor', () => {
		const { container } = render(Schedule, { props });
		expect(container.querySelector('section.schedule')?.id).toBe('schedule');
	});

	it('uses the desktop row and full day counts on a wide viewport', () => {
		wideViewport(true);
		const { container } = render(Schedule, { props });
		expect(container.querySelectorAll('.row.desktop')).toHaveLength(3);
		expect(container.querySelector('button.day .count')?.textContent?.trim()).toBe('1 game');
	});

	it('uses the mobile row and numeric day counts below 680px', () => {
		wideViewport(false);
		const { container } = render(Schedule, { props });
		expect(container.querySelectorAll('.row.mobile')).toHaveLength(3);
		expect(container.querySelector('button.day .count')?.textContent?.trim()).toBe('1');
	});

	it('marks the header mobile below 680px when the block sits below the heading', async () => {
		wideViewport(false);
		stubHeaderLayout(true);
		const { container } = render(Schedule, { props });
		await tick();
		expect(container.querySelector('section#schedule > header')?.classList.contains('mobile')).toBe(
			true
		);
	});

	it('does not mark the header mobile below 680px when it does not wrap', async () => {
		wideViewport(false);
		stubHeaderLayout(false);
		const { container } = render(Schedule, { props });
		await tick();
		expect(container.querySelector('section#schedule > header')?.classList.contains('mobile')).toBe(
			false
		);
	});

	it('does not mark the header mobile on a wide viewport or without matchMedia', () => {
		wideViewport(true);
		const wide = render(Schedule, { props });
		expect(
			wide.container.querySelector('section#schedule > header')?.classList.contains('mobile')
		).toBe(false);
		wide.unmount();
		vi.unstubAllGlobals();
		const bare = render(Schedule, { props });
		expect(
			bare.container.querySelector('section#schedule > header')?.classList.contains('mobile')
		).toBe(false);
	});

	it('plays the staggered entrance when the list first scrolls into view', async () => {
		stubEntrance();
		render(Schedule, { props });
		expect(animate).not.toHaveBeenCalled();
		callbacks[0]([{ isIntersecting: true }]);
		await tick();
		expect(animate).toHaveBeenCalledTimes(3);
	});

	it('hides the list until it first scrolls into view', async () => {
		stubEntrance();
		const { container } = render(Schedule, { props });
		await tick();
		const list = container.querySelector('.list')!;
		expect(list.classList.contains('waiting')).toBe(true);
		callbacks[0]([{ isIntersecting: true }]);
		await tick();
		expect(list.classList.contains('waiting')).toBe(false);
	});

	it('replays the list entrance when the day changes', async () => {
		stubEntrance();
		const { container } = render(Schedule, { props });
		callbacks[0]([{ isIntersecting: true }]);
		await tick();
		animate.mockClear();
		await fireEvent.click(cells(container)[2]);
		await tick();
		expect(animate).toHaveBeenCalledTimes(2);
	});

	it('does not replay when the selected day is clicked again', async () => {
		stubEntrance();
		const { container } = render(Schedule, { props });
		callbacks[0]([{ isIntersecting: true }]);
		await tick();
		animate.mockClear();
		await fireEvent.click(cells(container)[3]);
		await tick();
		expect(animate).not.toHaveBeenCalled();
	});

	it('shows the header in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(Schedule, { props });
		expect(screen.getByText('Calendario')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 2 }).textContent?.trim()).toBe(
			'domingo, 4 de octubre'
		);
		expect(screen.getAllByText('3 partidos').length).toBeGreaterThanOrEqual(1);
		expect(screen.getByText('Actualizado hace 3m')).toBeTruthy();
	});

	describe('open cards', () => {
		const detailed = (id: string): ScheduleGame => ({
			...game(id, 90),
			details: {
				kind: 'played',
				periods: { away: [20, 20, 20, 30], home: [25, 25, 25, 25] },
				leaders: {
					away: {
						firstName: 'A',
						lastName: 'One',
						team: team('GSW', 'Warriors', 'Golden State'),
						photo: '/a.svg',
						points: 1,
						rebounds: 2,
						assists: 3
					},
					home: {
						firstName: 'B',
						lastName: 'Two',
						team: team('LAL', 'Lakers', 'Los Angeles'),
						photo: '/b.svg',
						points: 1,
						rebounds: 2,
						assists: 3
					}
				},
				highlights: {
					platform: 'Test platform',
					searchUrl: '/search?q=x',
					videos: [
						{
							id: 'v1',
							title: `Clip ${id}`,
							channel: 'Channel',
							thumbnail: '/thumb.svg',
							embedUrl: '/embed/1'
						}
					]
				},
				stats: {
					away: { fieldGoalPct: 0.5, threePointPct: 0.4, rebounds: 40, assists: 20, turnovers: 10 },
					home: {
						fieldGoalPct: 0.45,
						threePointPct: 0.35,
						rebounds: 42,
						assists: 22,
						turnovers: 12
					}
				}
			}
		});
		const detailedProps = {
			updatedMinutesAgo: 3,
			gameHref,
			teamHref,
			selected: 3,
			days: [
				...days.slice(0, 3),
				{ date: days[3].date, games: [detailed('x'), detailed('y')] },
				...days.slice(4)
			]
		};
		const toggles = (container: HTMLElement) =>
			container.querySelectorAll<HTMLButtonElement>('button.toggle');
		const expanded = (container: HTMLElement) =>
			container.querySelectorAll('[aria-expanded="true"]');

		it('opens a game card when its row is clicked', async () => {
			const { container } = render(Schedule, { props: detailedProps });
			expect(expanded(container)).toHaveLength(0);
			await fireEvent.click(toggles(container)[0]);
			expect(toggles(container)[0].getAttribute('aria-expanded')).toBe('true');
		});

		it('links each open card to the detail page of its game', () => {
			const { container } = render(Schedule, { props: detailedProps });
			const links = [...container.querySelectorAll<HTMLAnchorElement>('a.game-center')];
			expect(links.map((a) => a.getAttribute('href'))).toEqual(['/game/x', '/game/y']);
		});

		it('opens the card whose id is bound to openId', () => {
			const { container } = render(Schedule, { props: { ...detailedProps, openId: 'y' } });
			expect(toggles(container)[0].getAttribute('aria-expanded')).toBe('false');
			expect(toggles(container)[1].getAttribute('aria-expanded')).toBe('true');
		});

		it('writes the opened card back to the bound openId', async () => {
			let bound: string | null = null;
			const bindable = {
				...detailedProps,
				get openId() {
					return bound;
				},
				set openId(value: string | null) {
					bound = value;
				}
			};
			const { container } = render(Schedule, { props: bindable });
			await fireEvent.click(toggles(container)[1]);
			expect(bound).toBe('y');
			await fireEvent.click(toggles(container)[1]);
			expect(bound).toBeNull();
		});

		it('gives each card an anchor id', () => {
			const { container } = render(Schedule, { props: detailedProps });
			expect([...container.querySelectorAll('ul.games > li')].map((li) => li.id)).toEqual([
				'game-x',
				'game-y'
			]);
		});

		it('closes the open card when another card is opened', async () => {
			const { container } = render(Schedule, { props: detailedProps });
			await fireEvent.click(toggles(container)[0]);
			await fireEvent.click(toggles(container)[1]);
			expect(expanded(container)).toHaveLength(1);
			expect(toggles(container)[1].getAttribute('aria-expanded')).toBe('true');
		});

		it('hides final scores behind Tap to reveal in spoiler-free mode and reveals them when the card opens', async () => {
			const { container } = render(Schedule, { props: { ...detailedProps, spoilerFree: true } });
			expect(container.querySelectorAll('button.toggle .score')).toHaveLength(0);
			expect(screen.getAllByText('Tap to reveal')).toHaveLength(2);
			await fireEvent.click(toggles(container)[0]);
			expect(toggles(container)[0].querySelectorAll('.score')).toHaveLength(2);
			expect(toggles(container)[1].querySelectorAll('.score')).toHaveLength(0);
			expect(screen.getAllByText('Tap to reveal')).toHaveLength(1);
		});

		it('shows the scores when spoiler-free mode is off', () => {
			const { container } = render(Schedule, { props: detailedProps });
			expect(container.querySelectorAll('button.toggle .score')).toHaveLength(4);
			expect(screen.queryByText('Tap to reveal')).toBeNull();
		});

		it('closes the open card when its row is clicked again', async () => {
			const { container } = render(Schedule, { props: detailedProps });
			await fireEvent.click(toggles(container)[0]);
			await fireEvent.click(toggles(container)[0]);
			expect(expanded(container)).toHaveLength(0);
		});

		const play = (container: HTMLElement) =>
			fireEvent.click(container.querySelector('li button.thumb') as HTMLButtonElement);

		it('plays a highlight in place when its thumbnail is clicked on the open card', async () => {
			const { container } = render(Schedule, { props: detailedProps });
			await fireEvent.click(toggles(container)[0]);
			await play(container);
			expect(container.querySelectorAll('iframe')).toHaveLength(1);
			expect(container.querySelector('iframe')?.getAttribute('src')).toBe('/embed/1');
		});

		it('stops the playing highlight when its card is closed', async () => {
			const { container } = render(Schedule, { props: detailedProps });
			await fireEvent.click(toggles(container)[0]);
			await play(container);
			await fireEvent.click(toggles(container)[0]);
			expect(container.querySelector('iframe')).toBeNull();
			await fireEvent.click(toggles(container)[0]);
			expect(container.querySelector('iframe')).toBeNull();
			expect(container.querySelector('li button.thumb')).not.toBeNull();
		});

		it('stops the playing highlight when another card is opened', async () => {
			const { container } = render(Schedule, { props: detailedProps });
			await fireEvent.click(toggles(container)[0]);
			await play(container);
			await fireEvent.click(toggles(container)[1]);
			expect(container.querySelector('iframe')).toBeNull();
		});

		it('stops the playing highlight when the day changes', async () => {
			const { container } = render(Schedule, { props: detailedProps });
			await fireEvent.click(toggles(container)[0]);
			await play(container);
			await fireEvent.click(cells(container)[4]);
			await fireEvent.click(cells(container)[3]);
			expect(toggles(container)[0].getAttribute('aria-expanded')).toBe('true');
			expect(container.querySelector('iframe')).toBeNull();
		});
	});

	it("links a card's team names to the page given by teamHref", () => {
		const { container } = render(Schedule, { props });
		const hrefs = [...container.querySelectorAll('li a')].map((a) => a.getAttribute('href'));
		expect(hrefs).toContain('/team/gsw');
		expect(hrefs).toContain('/team/lal');
		expect(container.querySelectorAll('button a, a a')).toHaveLength(0);
	});

	describe('empty-day box', () => {
		const emptyDay = {
			title: 'No games on this day',
			text: 'Next games: Tue, Oct 6 · 5 games',
			goTo: { date: '2026-10-06', label: 'Go to Tue, Oct 6 →' }
		};
		const windowHref = (date: string) => `/?day=${date}` as ResolvedPathname;

		it('shows the box instead of the no-games row on a day with no games', () => {
			render(Schedule, { props: { ...props, selected: 1, emptyDay, windowHref } });
			expect(screen.getByText('No games on this day')).toBeTruthy();
			expect(screen.queryByText('No games scheduled for this day.')).toBeNull();
		});

		it('shows the games and no box on a day with games', () => {
			render(Schedule, { props: { ...props, selected: 3, emptyDay, windowHref } });
			expect(screen.queryByText('No games on this day')).toBeNull();
		});

		it('keeps the old row without windowHref or without emptyDay', () => {
			const { unmount } = render(Schedule, { props: { ...props, selected: 1, emptyDay } });
			expect(screen.getByText('No games scheduled for this day.')).toBeTruthy();
			unmount();
			render(Schedule, { props: { ...props, selected: 1, windowHref } });
			expect(screen.getByText('No games scheduled for this day.')).toBeTruthy();
		});
	});
});
