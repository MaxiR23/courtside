// web/tests/lib/components/Hero.test.ts
//
// Tests for the Hero component.
//
// Tested:
// - Shows the status, kicker, heading, blurb and both actions
// - Calls the match details action; links All games to the schedule
// - Rotation through every game of the day, two stars each; the position "03 / 10" with several games
// - One game shows no position; no games shows the nav row only, with no timer
// - Delayed status in the status tag; Match details receives the game on screen
// - Slide indicator: starts on the away star, jumps on click, advances with autoplay
// - Progress fill: none with autoplay off, on the active item with autoplay
// - Spoiler-free toggle in the nav row: pressed state and callback
// - Parallax follows a mouse and is skipped on touch and with reduced motion
// - A games prop of the same length keeps the rotation position and the star timer
// - A delayed game reads "Scheduled" with the tip time and arena in the kicker, in English and Spanish
// - While the first feed loads: the skeleton of both columns, busy and hidden from assistive tech, gone once there is a game, shimmering unless motion is reduced
// - Shows the copy in Spanish with a Spanish browser preference
//
// What is covered:
// - Each state the hero shows, plus interaction
// - Fake timers, no real clock
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/Hero.test.ts
//
// SEE: web/src/lib/components/Hero.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { HeroGame, HeroPlayer } from '../../../src/lib/hero/types';
import { preferLanguages } from '../../prefer-languages';

import Hero from '../../../src/lib/components/Hero.svelte';

const star = (firstName: string, lastName: string, teamCode: string, teamName: string) =>
	({
		firstName,
		lastName,
		shortName: lastName,
		teamCode,
		teamName,
		photo: `/${lastName}.svg`
	}) satisfies HeroPlayer;

const oneGame: HeroGame = {
	id: 'g1',
	status: 'tonight',
	tipTime: '10:30 PM ET',
	arena: 'Chase Center',
	away: { name: 'Warriors', star: star('Stephen', 'Curry', 'GSW', 'Golden State Warriors') },
	home: { name: 'Lakers', star: star('LeBron', 'James', 'LAL', 'Los Angeles Lakers') }
};

// A game numbered n, whose stars are "AwayN" and "HomeN".
const numbered = (n: number): HeroGame => ({
	id: `g${n}`,
	status: 'tonight',
	tipTime: '7:00 PM ET',
	arena: `Arena ${n}`,
	away: { name: `Away Team ${n}`, star: star('A', `Away${n}`, 'AAA', `City Away ${n}`) },
	home: { name: `Home Team ${n}`, star: star('H', `Home${n}`, 'HHH', `City Home ${n}`) }
});
const games = (count: number) => Array.from({ length: count }, (_, i) => numbered(i + 1));

const baseProps = {
	games: [oneGame],
	today: new Date(2026, 9, 4, 12),
	scheduleHref: '/' as ResolvedPathname,
	onMatchDetails: () => {},
	spoilerFree: false,
	onSpoilerFreeToggle: () => {},
	autoplay: false
};

function mediaWith(matching: string[]) {
	vi.stubGlobal('matchMedia', (query: string) => ({ matches: matching.includes(query) }));
}

const FINE = '(hover: hover) and (pointer: fine)';
const REDUCED = '(prefers-reduced-motion: reduce)';

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
	Reflect.deleteProperty(HTMLElement.prototype, 'animate');
});

function indicatorItems(container: HTMLElement) {
	return container.querySelectorAll<HTMLButtonElement>('.indicator-item');
}

describe('Hero', () => {
	it('shows Tonight for a game tonight', () => {
		render(Hero, { props: baseProps });
		expect(screen.getByText('Tonight')).toBeTruthy();
	});

	it('shows Live now for a live game', () => {
		render(Hero, { props: { ...baseProps, games: [{ ...oneGame, status: 'live' as const }] } });
		expect(screen.getByText('Live now')).toBeTruthy();
	});

	it('shows Final for a finished game', () => {
		render(Hero, { props: { ...baseProps, games: [{ ...oneGame, status: 'final' as const }] } });
		expect(screen.getByText('Final')).toBeTruthy();
	});

	it('shows the tip time and arena in the kicker', () => {
		render(Hero, { props: baseProps });
		expect(screen.getByText('10:30 PM ET · Chase Center')).toBeTruthy();
	});

	it('shows the away team, then at and the home team in the heading', () => {
		render(Hero, { props: baseProps });
		const heading = screen.getByRole('heading', { level: 1 });
		expect(heading.textContent).toMatch(/^\s*Warriors\s*at\s+Lakers\s*$/);
	});

	it('shows the blurb naming both stars and the arena', () => {
		render(Hero, { props: baseProps });
		expect(screen.getByText('Stephen Curry and LeBron James meet at Chase Center.')).toBeTruthy();
	});

	it('calls the match details action with the game on screen when Match details is clicked', async () => {
		const onMatchDetails = vi.fn();
		render(Hero, { props: { ...baseProps, onMatchDetails } });
		await fireEvent.click(screen.getByRole('button', { name: 'Match details' }));
		expect(onMatchDetails).toHaveBeenCalledTimes(1);
		expect(onMatchDetails).toHaveBeenCalledWith('g1');
	});

	it('links All games to the schedule', () => {
		render(Hero, { props: { ...baseProps, scheduleHref: '/schedule' as ResolvedPathname } });
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/schedule');
	});

	it('starts on the away star in the slide indicator', () => {
		const { container } = render(Hero, { props: baseProps });
		const items = indicatorItems(container);
		expect(items[0].getAttribute('aria-current')).toBe('true');
		expect(items[0].textContent).toContain('01');
		expect(items[1].getAttribute('aria-current')).toBeNull();
		expect(container.querySelector('.watermark.active')?.textContent).toBe('Curry');
	});

	it('jumps to the home star when its indicator item is clicked', async () => {
		const { container } = render(Hero, { props: baseProps });
		await fireEvent.click(indicatorItems(container)[1]);
		expect(indicatorItems(container)[1].getAttribute('aria-current')).toBe('true');
		expect(container.querySelector('.watermark.active')?.textContent).toBe('James');
	});

	it('advances to the home star after 7 seconds with autoplay', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, { props: { ...baseProps, autoplay: true } });
		await tick();
		vi.advanceTimersByTime(7000);
		await tick();
		expect(indicatorItems(container)[1].getAttribute('aria-current')).toBe('true');
	});

	it('shows no progress fill when autoplay is off', async () => {
		const { container } = render(Hero, { props: baseProps });
		await tick();
		expect(container.querySelector('.fill')).toBeNull();
	});

	it("fills the active item's track with autoplay", async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, { props: { ...baseProps, autoplay: true } });
		await tick();
		const fills = container.querySelectorAll('.fill');
		expect(fills).toHaveLength(1);
		expect(indicatorItems(container)[0].contains(fills[0])).toBe(true);
	});

	it('stays on the first slide when autoplay is off', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, { props: baseProps });
		await tick();
		vi.advanceTimersByTime(30000);
		await tick();
		expect(indicatorItems(container)[0].getAttribute('aria-current')).toBe('true');
	});

	it('tracks the pointer for parallax with a mouse', async () => {
		mediaWith([FINE]);
		vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
			left: 0,
			top: 0,
			width: 200,
			height: 100
		} as DOMRect);
		const { container } = render(Hero, { props: baseProps });
		await tick();
		const section = container.querySelector('.hero') as HTMLElement;
		await fireEvent.mouseMove(section, { clientX: 200, clientY: 100 });
		expect(section.style.getPropertyValue('--pointer-x')).toBe('1');
		expect(section.style.getPropertyValue('--pointer-y')).toBe('1');
	});

	it('resets the parallax when the mouse leaves', async () => {
		mediaWith([FINE]);
		vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
			left: 0,
			top: 0,
			width: 200,
			height: 100
		} as DOMRect);
		const { container } = render(Hero, { props: baseProps });
		await tick();
		const section = container.querySelector('.hero') as HTMLElement;
		await fireEvent.mouseMove(section, { clientX: 200, clientY: 100 });
		await fireEvent.mouseLeave(section);
		expect(section.style.getPropertyValue('--pointer-x')).toBe('0');
	});

	it('skips parallax on a touch device', async () => {
		mediaWith([]);
		const { container } = render(Hero, { props: baseProps });
		await tick();
		const section = container.querySelector('.hero') as HTMLElement;
		await fireEvent.mouseMove(section, { clientX: 200, clientY: 100 });
		expect(section.style.getPropertyValue('--pointer-x')).toBe('0');
	});

	it('skips parallax when reduced motion is requested', async () => {
		mediaWith([FINE, REDUCED]);
		const { container } = render(Hero, { props: baseProps });
		await tick();
		const section = container.querySelector('.hero') as HTMLElement;
		await fireEvent.mouseMove(section, { clientX: 200, clientY: 100 });
		expect(section.style.getPropertyValue('--pointer-x')).toBe('0');
	});

	it('shows the hero copy in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(Hero, { props: baseProps });
		expect(screen.getByText('Esta noche')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('en');
		expect(
			screen.getByText('Stephen Curry y LeBron James se enfrentan en Chase Center.')
		).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Detalles del partido' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Todos los partidos' })).toBeTruthy();
	});

	it('shows the spoiler-free toggle in the nav row, pressed when the mode is on', () => {
		render(Hero, { props: { ...baseProps, spoilerFree: true } });
		expect(screen.getByRole('button', { name: 'Spoiler-free' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
	});

	it('calls onSpoilerFreeToggle when the nav row toggle is clicked', async () => {
		const onSpoilerFreeToggle = vi.fn();
		render(Hero, { props: { ...baseProps, onSpoilerFreeToggle } });
		await fireEvent.click(screen.getByRole('button', { name: 'Spoiler-free' }));
		expect(onSpoilerFreeToggle).toHaveBeenCalledTimes(1);
	});
});

describe('Hero with several games', () => {
	const activeWatermark = (container: HTMLElement) =>
		container.querySelector('.watermark.active')?.textContent;
	const position = (container: HTMLElement) =>
		container.querySelector('.position')?.textContent?.replace(/\s+/g, ' ').trim();

	it('rotates to the next game after both stars (14 seconds)', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, {
			props: { ...baseProps, games: games(3), autoplay: true }
		});
		await tick();
		expect(activeWatermark(container)).toBe('Away1');
		vi.advanceTimersByTime(7000);
		await tick();
		expect(activeWatermark(container)).toBe('Home1');
		expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Away Team 1');
		vi.advanceTimersByTime(7000);
		await tick();
		expect(activeWatermark(container)).toBe('Away2');
		expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Away Team 2');
		expect(position(container)).toBe('02 / 03');
	});

	it('returns to the first game after the last', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, {
			props: { ...baseProps, games: games(2), autoplay: true }
		});
		await tick();
		vi.advanceTimersByTime(7000 * 4);
		await tick();
		expect(activeWatermark(container)).toBe('Away1');
		expect(position(container)).toBe('01 / 02');
	});

	it('shows the position 03 / 10 on the third of ten games', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, {
			props: { ...baseProps, games: games(10), autoplay: true }
		});
		await tick();
		vi.advanceTimersByTime(7000 * 4);
		await tick();
		expect(position(container)).toBe('03 / 10');
	});

	it('shows the two stars of the game on screen in the indicator', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, {
			props: { ...baseProps, games: games(3), autoplay: true }
		});
		await tick();
		vi.advanceTimersByTime(7000 * 2);
		await tick();
		const items = indicatorItems(container);
		expect(items).toHaveLength(2);
		expect(items[0].textContent).toContain('Away2');
		expect(items[1].textContent).toContain('Home2');
		await fireEvent.click(items[1]);
		expect(activeWatermark(container)).toBe('Home2');
	});

	it('passes the game on screen to Match details', async () => {
		vi.useFakeTimers();
		const onMatchDetails = vi.fn();
		render(Hero, {
			props: { ...baseProps, games: games(3), onMatchDetails, autoplay: true }
		});
		await tick();
		vi.advanceTimersByTime(7000 * 2);
		await tick();
		await fireEvent.click(screen.getByRole('button', { name: 'Match details' }));
		expect(onMatchDetails).toHaveBeenCalledWith('g2');
	});

	it('keeps the rotation when the games prop is replaced by one of the same length', async () => {
		vi.useFakeTimers();
		const { container, rerender } = render(Hero, {
			props: { ...baseProps, games: games(3), autoplay: true }
		});
		await tick();
		vi.advanceTimersByTime(7000 * 2);
		await tick();
		await rerender({ games: games(3) });
		expect(activeWatermark(container)).toBe('Away2');
		expect(position(container)).toBe('02 / 03');
	});

	it('does not restart the star timer when the games prop is replaced by one of the same length', async () => {
		vi.useFakeTimers();
		const { container, rerender } = render(Hero, {
			props: { ...baseProps, games: games(2), autoplay: true }
		});
		await tick();
		vi.advanceTimersByTime(5000);
		await tick();
		await rerender({ games: games(2) });
		vi.advanceTimersByTime(2500);
		await tick();
		expect(activeWatermark(container)).toBe('Home1');
	});
});

describe('Hero with one game or none', () => {
	it('does not show the position with one game', () => {
		const { container } = render(Hero, { props: baseProps });
		expect(container.querySelector('.position')).toBeNull();
	});

	it('shows Delayed in the status tag for a delayed game', () => {
		render(Hero, { props: { ...baseProps, games: [{ ...oneGame, status: 'delayed' }] } });
		expect(screen.getByText('Delayed')).toBeTruthy();
	});

	it('shows Delayed in the tag and Scheduled with the tip time and arena in the kicker for a delayed game', () => {
		render(Hero, { props: { ...baseProps, games: [{ ...oneGame, status: 'delayed' }] } });
		expect(screen.getByText('Delayed')).toBeTruthy();
		expect(screen.getByText('Scheduled 10:30 PM ET · Chase Center')).toBeTruthy();
	});

	it('shows the delayed kicker in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(Hero, { props: { ...baseProps, games: [{ ...oneGame, status: 'delayed' }] } });
		expect(screen.getByText('Retrasado')).toBeTruthy();
		expect(screen.getByText('Programado 10:30 PM ET · Chase Center')).toBeTruthy();
	});

	it('shows only the nav row and no timer with no games', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, { props: { ...baseProps, games: [], autoplay: true } });
		await tick();
		expect(vi.getTimerCount()).toBe(0);
		expect(container.querySelector('.columns')).toBeNull();
		expect(container.querySelector('.watermark')).toBeNull();
		expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
		expect(screen.getByRole('button', { name: 'Spoiler-free' })).toBeTruthy();
	});
});

describe('Hero while the first feed loads', () => {
	const loadingProps = { ...baseProps, games: [], loading: true };
	const count = (container: HTMLElement, selector: string) =>
		container.querySelectorAll(selector).length;

	it('shows the skeleton of both columns while loading', () => {
		const { container } = render(Hero, { props: loadingProps });
		expect(container.querySelector('.hero-skeleton')).not.toBeNull();
		expect(count(container, '.tag-bone')).toBe(1);
		expect(count(container, '.kicker-bone')).toBe(1);
		expect(count(container, '.headline-bone')).toBe(2);
		expect(count(container, '.blurb-bone')).toBe(1);
		expect(count(container, '.button-bone')).toBe(2);
		expect(count(container, '.indicator-bone')).toBe(2);
		expect(count(container, '.frame-bone')).toBe(1);
		expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
		expect(screen.queryByRole('button', { name: 'Match details' })).toBeNull();
		expect(screen.getByRole('button', { name: 'Spoiler-free' })).toBeTruthy();
	});

	it('marks the hero busy and hides the skeleton from assistive tech', () => {
		const { container } = render(Hero, { props: loadingProps });
		expect(container.querySelector('section.hero')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.hero-skeleton')?.getAttribute('aria-hidden')).toBe('true');
	});

	it('shows the game, not the skeleton, once there is a game', () => {
		const { container } = render(Hero, { props: { ...baseProps, loading: true } });
		expect(container.querySelector('.hero-skeleton')).toBeNull();
		expect(container.querySelector('section.hero')?.getAttribute('aria-busy')).toBeNull();
		expect(screen.getByRole('heading', { level: 1 })).toBeTruthy();
	});

	it('shows no skeleton when not loading', () => {
		const { container } = render(Hero, { props: { ...baseProps, games: [] } });
		expect(container.querySelector('.hero-skeleton')).toBeNull();
		expect(container.querySelector('section.hero')?.getAttribute('aria-busy')).toBeNull();
	});

	it('shimmers the skeleton, and not with reduced motion', () => {
		const animate = vi.fn<(keyframes: unknown, options: unknown) => { cancel: () => void }>(() => ({
			cancel: vi.fn()
		}));
		Object.assign(HTMLElement.prototype, { animate });
		const looped = () =>
			animate.mock.calls.some(
				(call) => (call[1] as { iterations?: number } | undefined)?.iterations === Infinity
			);
		mediaWith([]);
		const first = render(Hero, { props: loadingProps });
		expect(looped()).toBe(true);
		first.unmount();
		animate.mockClear();
		mediaWith([REDUCED]);
		render(Hero, { props: loadingProps });
		expect(looped()).toBe(false);
		expect(animate).not.toHaveBeenCalled();
	});
});
