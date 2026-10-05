// web/tests/lib/components/Hero.test.ts
//
// Tests for the Hero component.
//
// Tested:
// - Shows the status, kicker, heading, blurb and both actions
// - Calls the match details action; links All games to the schedule
// - Slide indicator: starts on the away star, jumps on click, advances with autoplay
// - Spoiler-free toggle in the nav row: pressed state and callback
// - Parallax follows a mouse and is skipped on touch and with reduced motion
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

import type { HeroPlayer } from '../../../src/lib/hero/types';
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

const baseProps = {
	status: 'tonight' as const,
	tipTime: '10:30 PM ET',
	arena: 'Chase Center',
	away: { name: 'Warriors', star: star('Stephen', 'Curry', 'GSW', 'Golden State Warriors') },
	home: { name: 'Lakers', star: star('LeBron', 'James', 'LAL', 'Los Angeles Lakers') },
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
		render(Hero, { props: { ...baseProps, status: 'live' } });
		expect(screen.getByText('Live now')).toBeTruthy();
	});

	it('shows Final for a finished game', () => {
		render(Hero, { props: { ...baseProps, status: 'final' } });
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

	it('calls the match details action when Match details is clicked', async () => {
		const onMatchDetails = vi.fn();
		render(Hero, { props: { ...baseProps, onMatchDetails } });
		await fireEvent.click(screen.getByRole('button', { name: 'Match details' }));
		expect(onMatchDetails).toHaveBeenCalledTimes(1);
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
