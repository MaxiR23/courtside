// web/tests/lib/components/Schedule.test.ts
//
// Tests for the Schedule component.
//
// Tested:
// - Header: kicker, selected day, game count, freshness; today selected by default
// - Selecting a day changes the heading, count and games; a day with no games shows the day, 0 games and the no-games message
// - Desktop row and full counts on a wide viewport; mobile row and numbers below it
// - The staggered list entrance on first view and on a day change, not on the same day
// - The list is hidden until it first scrolls into view
// - Only one game card is open at a time; clicking an open card closes it
// - The open card can be bound from outside; each card has an anchor id; the section has the schedule anchor
// - The playing highlight stops when its card closes, another opens or the day changes
// - Spoiler-free mode hides final scores until a card opens
// - Spanish copy, including the no-games message, with a Spanish browser preference
//
// What is covered:
// - Each state, including a day with no games, plus interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/Schedule.test.ts
//
// SEE: web/src/lib/components/Schedule.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ScheduleDay, ScheduleGame } from '../../../src/lib/schedule/types';
import { preferLanguages } from '../../prefer-languages';

import Schedule from '../../../src/lib/components/Schedule.svelte';

const team = (code: string, name: string, city: string) => ({ code, name, city });
const game = (id: string, awayScore: number): ScheduleGame => ({
	id,
	away: team('GSW', 'Warriors', 'Golden State'),
	home: team('LAL', 'Lakers', 'Los Angeles'),
	status: { state: 'final', awayScore, homeScore: 100 }
});
const counts = [1, 0, 2, 3, 1, 1, 1];
const days: ScheduleDay[] = counts.map((n, i) => ({
	date: new Date(2026, 9, 1 + i, 12),
	games: Array.from({ length: n }, (_, k) => game(`${i}-${k}`, 90 + k))
}));
const props = { days, updatedMinutesAgo: 3 };

function wideViewport(wide: boolean) {
	vi.stubGlobal('matchMedia', (query: string) => ({
		matches: query.includes('min-width') ? wide : false,
		addEventListener: () => {},
		removeEventListener: () => {}
	}));
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
	it('shows the SCHEDULE kicker, the selected day, the game count and the freshness label', () => {
		render(Schedule, { props });
		expect(screen.getByText('Schedule')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 2 }).textContent?.trim()).toBe('Sunday, October 4');
		expect(screen.getAllByText('3 games').length).toBeGreaterThanOrEqual(1);
		expect(screen.getByText('Updated 3 min ago')).toBeTruthy();
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
		expect(screen.getByText('Actualizado hace 3 min')).toBeTruthy();
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
						teamCode: 'GSW',
						photo: '/a.svg',
						points: 1,
						rebounds: 2,
						assists: 3
					},
					home: {
						firstName: 'B',
						lastName: 'Two',
						teamCode: 'LAL',
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
});
