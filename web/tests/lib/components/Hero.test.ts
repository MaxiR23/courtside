// web/tests/lib/components/Hero.test.ts
//
// Tests for the Hero component.
//
// Tested:
// - Shows the status, kicker, heading, blurb and both actions
// - Calls the match details action; links All games to the schedule
// - Rotation through every game of the day, two stars each; the position "03 / 10" with several games
// - One game shows no position; no games shows the nav row only, with no timer
// - Both headline team names link to the team page
// - Delayed status in the status tag; Match details receives the game on screen
// - Slide selectors: start on the away star, jump on click, advance after 5 seconds with autoplay and restart the wait on a click
// - The away and home logos in the title and the selectors; the tricode, the background word and the card layers of the active side
// - A side with no logo and no accent shows the monogram and the neutral accent
// - A new featured game starts at its away slide; a games prop of another length resets to the first game
// - Reduced motion: no animated track fill, and a click still changes the slide
// - Progress fill: none with autoplay off, on the active item with autoplay
// - Spoiler-free toggle in the nav row: pressed state and callback
// - Parallax follows a mouse and is skipped on touch and with reduced motion
// - A games prop of the same length keeps the rotation position and the star timer
// - Without an arena the kicker is the tip time alone and the blurb is left out (ADR 0064)
// - A delayed game reads "Scheduled" with the tip time and arena in the kicker, in English and Spanish
// - While the first feed loads: the skeleton of both columns, busy and hidden from assistive tech, gone once there is a game, shimmering unless motion is reduced
// - Shows the copy in Spanish with a Spanish browser preference
// - Photo change: the outgoing cutout fades out over the shorter token, its outline drops at once, the incoming outline returns after the settle; logo and tricode keep their timing
// - A day with no games and a noGames view: the nav row and the no-games title, with no slide selector, position or timer; the skeleton still comes first while loading
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
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { HeroGame, HeroPlayer, HeroSide } from '../../../src/lib/hero/types';
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

const marinersLogo = {
	light: 'https://example.com/hbr-light.svg',
	dark: 'https://example.com/hbr-dark.svg'
};
const owlsLogo = { light: 'https://example.com/pvo-light.svg', dark: null };

const side = (
	code: string,
	name: string,
	city: string,
	starOf: HeroPlayer,
	identity: Partial<Pick<HeroSide, 'logo' | 'accent'>> = {}
): HeroSide => ({
	code,
	name,
	city,
	guest: false,
	logo: null,
	accent: null,
	...identity,
	star: starOf
});

const oneGame: HeroGame = {
	id: 'g1',
	status: 'tonight',
	tipTime: '10:30 PM',
	arena: 'Harbor Arena',
	away: side(
		'HBR',
		'Mariners',
		'Harbor City',
		star('Ines', 'Varga', 'HBR', 'Harbor City Mariners'),
		{
			logo: marinersLogo,
			accent: '#1f6f8b'
		}
	),
	home: side('PVO', 'Owls', 'Pine Valley', star('Tomas', 'Okafor', 'PVO', 'Pine Valley Owls'), {
		logo: owlsLogo,
		accent: '#c9822b'
	})
};

// A game numbered n, whose stars are "AwayN" and "HomeN".
const numbered = (n: number): HeroGame => ({
	id: `g${n}`,
	status: 'tonight',
	tipTime: '7:00 PM',
	arena: `Arena ${n}`,
	away: side('AAA', `Away Team ${n}`, 'City', star('A', `Away${n}`, 'AAA', `City Away ${n}`)),
	home: side('HHH', `Home Team ${n}`, 'City', star('H', `Home${n}`, 'HHH', `City Home ${n}`))
});
const games = (count: number) => Array.from({ length: count }, (_, i) => numbered(i + 1));

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;

const baseProps = {
	teamHref,
	games: [oneGame],
	today: new Date(2026, 9, 4, 12),
	scheduleHref: '/' as ResolvedPathname,
	standingsHref: '/standings' as ResolvedPathname,
	layout: 'desktop' as const,
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
	return container.querySelectorAll<HTMLButtonElement>('button.selector');
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
		expect(screen.getByText('10:30 PM · Harbor Arena')).toBeTruthy();
	});

	it('shows the tip time alone in the kicker and no blurb when the arena is unknown', () => {
		const { container } = render(Hero, {
			props: { ...baseProps, games: [{ ...oneGame, arena: null }] }
		});
		expect(screen.getByText('10:30 PM')).toBeTruthy();
		expect(container.textContent).not.toContain('·');
		expect(container.querySelector('.blurb')).toBeNull();
		expect(screen.queryByText(/meet at/)).toBeNull();
	});

	it('shows the away team, then at and the home team in the heading', () => {
		render(Hero, { props: baseProps });
		const heading = screen.getByRole('heading', { level: 1 });
		expect(heading.textContent).toMatch(/^\s*Mariners\s*at\s+Owls\s*$/);
	});

	it('shows the blurb naming both stars and the arena', () => {
		render(Hero, { props: baseProps });
		expect(screen.getByText('Ines Varga and Tomas Okafor meet at Harbor Arena.')).toBeTruthy();
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
		expect(items[1].getAttribute('aria-current')).toBeNull();
		expect(container.querySelector('.word.active')?.textContent).toBe('Varga');
	});

	it('jumps to the home star when its indicator item is clicked', async () => {
		const { container } = render(Hero, { props: baseProps });
		await fireEvent.click(indicatorItems(container)[1]);
		expect(indicatorItems(container)[1].getAttribute('aria-current')).toBe('true');
		expect(container.querySelector('.word.active')?.textContent).toBe('Okafor');
	});

	it('advances to the home star after 5 seconds with autoplay', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, { props: { ...baseProps, autoplay: true } });
		await tick();
		vi.advanceTimersByTime(5000);
		await tick();
		expect(indicatorItems(container)[1].getAttribute('aria-current')).toBe('true');
	});

	it('shows no progress fill when autoplay is off', async () => {
		const { container } = render(Hero, { props: baseProps });
		await tick();
		expect(container.querySelector('.track-fill')).toBeNull();
	});

	it("fills the active item's track with autoplay", async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, { props: { ...baseProps, autoplay: true } });
		await tick();
		const fills = container.querySelectorAll('.track-fill');
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
			screen.getByText('Ines Varga y Tomas Okafor se enfrentan en Harbor Arena.')
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
		container.querySelector('.word.active')?.textContent;
	const position = (container: HTMLElement) =>
		container.querySelector('.position')?.textContent?.replace(/\s+/g, ' ').trim();

	it('rotates to the next game after both stars (10 seconds)', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, {
			props: { ...baseProps, games: games(3), autoplay: true }
		});
		await tick();
		expect(activeWatermark(container)).toBe('Away1');
		vi.advanceTimersByTime(5000);
		await tick();
		expect(activeWatermark(container)).toBe('Home1');
		expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Away Team 1');
		vi.advanceTimersByTime(5000);
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
		vi.advanceTimersByTime(5000 * 4);
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
		vi.advanceTimersByTime(5000 * 4);
		await tick();
		expect(position(container)).toBe('03 / 10');
	});

	it('shows the two stars of the game on screen in the indicator', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, {
			props: { ...baseProps, games: games(3), autoplay: true }
		});
		await tick();
		vi.advanceTimersByTime(5000 * 2);
		await tick();
		const items = indicatorItems(container);
		expect(items).toHaveLength(2);
		expect(items[0].textContent).toContain('Away Team 2');
		expect(items[1].textContent).toContain('Home Team 2');
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
		vi.advanceTimersByTime(5000 * 2);
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
		vi.advanceTimersByTime(5000 * 2);
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
		vi.advanceTimersByTime(3000);
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
		expect(screen.getByText('Scheduled 10:30 PM · Harbor Arena')).toBeTruthy();
	});

	it('shows the delayed kicker in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(Hero, { props: { ...baseProps, games: [{ ...oneGame, status: 'delayed' }] } });
		expect(screen.getByText('Retrasado')).toBeTruthy();
		expect(screen.getByText('Programado 10:30 PM · Harbor Arena')).toBeTruthy();
	});

	it('shows only the nav row and no timer with no games', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, { props: { ...baseProps, games: [], autoplay: true } });
		await tick();
		expect(vi.getTimerCount()).toBe(0);
		expect(container.querySelector('.columns')).toBeNull();
		expect(container.querySelector('.word')).toBeNull();
		expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
		expect(screen.getByRole('button', { name: 'Spoiler-free' })).toBeTruthy();
	});
});

describe('Hero on a day with no games', () => {
	const noGames = {
		date: 'Sunday, October 4',
		tag: 'Off day',
		paragraph: 'A rest day across the league.',
		nextTipOff: null,
		broadcast: null,
		comingUp: null
	};

	it('shows the nav row and the no-games title, with no rotation and no timer', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, {
			props: { ...baseProps, games: [], autoplay: true, noGames }
		});
		await tick();
		expect(vi.getTimerCount()).toBe(0);
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('No games today');
		expect(screen.getByRole('button', { name: 'Spoiler-free' })).toBeTruthy();
		expect(container.querySelector('.position')).toBeNull();
		expect(container.querySelector('.indicator')).toBeNull();
		expect(container.querySelector('.word')).toBeNull();
	});

	it('still shows the skeleton while the first feed loads', () => {
		const { container } = render(Hero, {
			props: { ...baseProps, games: [], loading: true, noGames }
		});
		expect(container.querySelector('.hero-skeleton')).not.toBeNull();
		expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
	});
});

describe('Hero while the first feed loads', () => {
	const loadingProps = { ...baseProps, games: [], loading: true };
	const count = (container: HTMLElement, selector: string) =>
		container.querySelectorAll(selector).length;

	it('shows the skeleton of both columns while loading', () => {
		const { container } = render(Hero, { props: loadingProps });
		expect(container.querySelector('.hero-skeleton')).not.toBeNull();
		expect(count(container, '.hero-skeleton .bone')).toBe(10);
		expect(count(container, '.tag .bone')).toBe(2);
		expect(count(container, '.copy > .bone')).toBe(3);
		expect(count(container, '.buttons .bone')).toBe(2);
		expect(count(container, '.indicator .bone')).toBe(2);
		expect(count(container, '.frame-bone-wrap .bone')).toBe(1);
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

	it('links both headline team names to the team page', () => {
		render(Hero, { props: baseProps });
		const heading = screen.getByRole('heading', { level: 1 });
		const links = [...heading.querySelectorAll('a')];
		expect(links.map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
			['Mariners', '/team/hbr'],
			['Owls', '/team/pvo']
		]);
	});

	it('passes Home through to the nav row: Games current, Standings linked', async () => {
		render(Hero, {
			props: {
				...baseProps,
				standingsHref: '/standings' as ResolvedPathname
			}
		});
		const games = screen.getByRole('link', { name: 'Games' });
		expect(games.getAttribute('aria-current')).toBe('page');
		const standings = screen.getByRole('link', { name: 'Standings' });
		expect(standings.getAttribute('href')).toBe('/standings');
		expect(standings.getAttribute('aria-current')).toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		const cup = screen.getByRole('link', { name: 'Cup' });
		expect(cup.getAttribute('href')).toBe('/cup');
		expect(cup.getAttribute('aria-current')).toBeNull();
	});
});

describe('Hero team identity', () => {
	const NEUTRAL = 'var(--identity-neutral-accent)';
	const accentOf = (el: Element | null) =>
		(el as HTMLElement).style.getPropertyValue('--side-accent');

	it('renders the away and home logos in the title and in the selectors', () => {
		const { container } = render(Hero, { props: baseProps });
		const srcs = (selector: string) =>
			[...container.querySelectorAll(`${selector} img`)].map((img) => img.getAttribute('src'));
		expect(srcs('.headline')).toEqual([
			'https://example.com/hbr-dark.svg',
			'https://example.com/pvo-light.svg'
		]);
		expect(srcs('.indicator')).toEqual([
			'https://example.com/hbr-dark.svg',
			'https://example.com/pvo-light.svg'
		]);
	});

	it('renders the tricode, the background word and the card layers of the active side', () => {
		const { container } = render(Hero, { props: baseProps });
		expect([...container.querySelectorAll('.tricode')].map((t) => t.textContent?.trim())).toEqual([
			'HBR',
			'PVO'
		]);
		expect(container.querySelector('.word.active')?.textContent).toBe('Varga');
		expect(accentOf(container.querySelector('.word.active'))).toBe('#1f6f8b');
		expect(container.querySelector('.slide:not([aria-hidden]) .logo-layer img')).not.toBeNull();
		expect(container.querySelector('.strip')?.textContent).toContain('Ines Varga');
		expect(accentOf(container.querySelector('.player-card'))).toBe('#1f6f8b');
	});

	it('shows the monogram and the neutral accent for a side with no logo and no accent', () => {
		const bare = {
			...oneGame,
			home: { ...oneGame.home, logo: null, accent: null }
		};
		const { container } = render(Hero, { props: { ...baseProps, games: [bare] } });
		const home = container.querySelectorAll('button.selector')[1];
		expect(home.querySelector('img')).toBeNull();
		expect(home.querySelector('.team-monogram')?.textContent).toBe('PVO');
		expect(accentOf(home)).toBe(NEUTRAL);
		expect(container.querySelectorAll('.headline img')).toHaveLength(1);
		expect(container.querySelectorAll('.headline .title-logo')).toHaveLength(2);
		for (const mark of container.querySelectorAll('.headline .title-logo')) {
			expect(mark.getAttribute('aria-hidden')).toBe('true');
		}
		expect(screen.getByRole('heading', { level: 1, name: /^Mariners\s*at\s+Owls$/ })).toBeTruthy();
		expect(container.querySelectorAll('.headline .team-monogram:not(.logo)')).toHaveLength(1);
		expect(accentOf(container.querySelectorAll('.slide')[1])).toBe(NEUTRAL);
		// The other side keeps its accent.
		expect(accentOf(container.querySelectorAll('button.selector')[0])).toBe('#1f6f8b');
		expect(accentOf(container.querySelectorAll('.word')[1])).toBe(NEUTRAL);
	});

	it('names the selectors for the away and the home team', () => {
		render(Hero, { props: baseProps });
		expect(screen.getByRole('button', { name: 'Show Mariners, away' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Show Owls, home' })).toBeTruthy();
	});
});

describe('Hero slide timing', () => {
	const current = (container: HTMLElement) =>
		container.querySelector('button.selector[aria-current="true"]')?.getAttribute('aria-label');

	it('starts at the away slide', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, { props: { ...baseProps, autoplay: true } });
		await tick();
		expect(current(container)).toBe('Show Mariners, away');
	});

	it('advances to the home slide after 5 seconds and not before', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, { props: { ...baseProps, autoplay: true } });
		await tick();
		vi.advanceTimersByTime(4999);
		await tick();
		expect(current(container)).toBe('Show Mariners, away');
		vi.advanceTimersByTime(1);
		await tick();
		expect(current(container)).toBe('Show Owls, home');
	});

	it('goes to the clicked slide and restarts the timer', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, { props: { ...baseProps, autoplay: true } });
		await tick();
		vi.advanceTimersByTime(3000);
		await tick();
		await fireEvent.click(screen.getByRole('button', { name: 'Show Owls, home' }));
		expect(current(container)).toBe('Show Owls, home');
		vi.advanceTimersByTime(4999);
		await tick();
		expect(current(container)).toBe('Show Owls, home');
		vi.advanceTimersByTime(1);
		await tick();
		expect(current(container)).toBe('Show Mariners, away');
	});

	it('starts a new featured game at its away slide', async () => {
		vi.useFakeTimers();
		const { container } = render(Hero, {
			props: { ...baseProps, games: games(2), autoplay: true }
		});
		await tick();
		vi.advanceTimersByTime(10000);
		await tick();
		expect(current(container)).toBe('Show Away Team 2, away');
		expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Away Team 2');
	});

	it('resets to the away slide of the first game when the games prop has another length', async () => {
		vi.useFakeTimers();
		const { container, rerender } = render(Hero, {
			props: { ...baseProps, games: games(3), autoplay: true }
		});
		await tick();
		vi.advanceTimersByTime(10000);
		await tick();
		expect(current(container)).toBe('Show Away Team 2, away');
		await rerender({ games: games(2) });
		expect(current(container)).toBe('Show Away Team 1, away');
	});

	it('does not animate the track fill with reduced motion, and a click still changes the slide', async () => {
		const animate = vi.fn(() => ({ cancel: vi.fn() }));
		Object.assign(HTMLElement.prototype, { animate });
		mediaWith([REDUCED]);
		const { container } = render(Hero, { props: { ...baseProps, autoplay: true } });
		await tick();
		expect(container.querySelectorAll('.track-fill')).toHaveLength(1);
		await fireEvent.click(screen.getByRole('button', { name: 'Show Owls, home' }));
		expect(current(container)).toBe('Show Owls, home');
		expect(animate).not.toHaveBeenCalled();
	});
});

describe('Hero photo change', () => {
	const tokens = {
		'--hero-crossfade-duration': '1s',
		'--hero-crossfade-out-duration': '0.15s',
		'--identity-settle-duration': '1.2s',
		'--ease': 'linear',
		'--hero-cutout-outline': 'drop-shadow(0 0 1px red)',
		'--hero-cutout-outline-off': 'drop-shadow(0 0 0 transparent)',
		'--hero-cutout-shade': 'drop-shadow(0 30px 30px black) contrast(1.05)'
	};

	beforeEach(() => {
		for (const [name, value] of Object.entries(tokens)) {
			document.documentElement.style.setProperty(name, value);
		}
	});

	afterEach(() => {
		for (const name of Object.keys(tokens)) document.documentElement.style.removeProperty(name);
	});

	type Call = { target: Element; keyframes: Keyframe[]; options: KeyframeAnimationOptions };

	async function changePhoto() {
		const animate = vi.fn((keyframes: Keyframe[], options: KeyframeAnimationOptions) => ({
			cancel: vi.fn(),
			keyframes,
			options
		}));
		Object.assign(HTMLElement.prototype, { animate });
		mediaWith([]);
		const { container } = render(Hero, { props: baseProps });
		await tick();
		animate.mockClear();
		await fireEvent.click(screen.getByRole('button', { name: 'Show Owls, home' }));
		const calls: Call[] = animate.mock.calls.map(([keyframes, options], i) => ({
			target: animate.mock.contexts[i] as Element,
			keyframes,
			options
		}));
		const cutouts = container.querySelectorAll('.cutout');
		const on = (el: Element | null | undefined) => calls.filter((c) => c.target === el);
		return { container, calls, cutouts, on };
	}

	it('fades the outgoing photo out faster than the incoming one rises', async () => {
		const { cutouts, on } = await changePhoto();
		expect(on(cutouts[0])[0].options.duration).toBe(150);
		const incoming = on(cutouts[1])[0];
		expect(incoming.options.duration).toBe(1000);
		expect(incoming.keyframes[0].opacity).toBe(0);
		expect(String(incoming.keyframes[0].transform)).toContain('translateY');
	});

	it('drops the outline of the outgoing photo at once', async () => {
		const { cutouts, on } = await changePhoto();
		expect(on(cutouts[0].querySelector('img'))).toHaveLength(0);
		expect(cutouts[0].classList.contains('active')).toBe(false);
	});

	it('brings the outline back on the incoming photo only after it settles', async () => {
		const { cutouts, on } = await changePhoto();
		const [call] = on(cutouts[1].querySelector('img'));
		expect(call.options.delay).toBe(1000);
		expect(call.options.fill).toBe('backwards');
		expect(call.options.duration).toBe(1000);
		expect(call.keyframes).toEqual([
			{ filter: 'drop-shadow(0 0 0 transparent) drop-shadow(0 30px 30px black) contrast(1.05)' },
			{ filter: 'var(--hero-cutout-filter)' }
		]);
	});

	it('keeps the logo and the tricode on the identity settle duration', async () => {
		const { container, calls } = await changePhoto();
		const settled = calls.filter(
			(c) => c.target.matches('.logo-layer, .tricode') && container.contains(c.target)
		);
		expect(settled.length).toBeGreaterThan(0);
		for (const c of settled) expect(c.options.duration).toBe(1200);
		const slides = calls.filter((c) => c.target.matches('.slide'));
		expect(slides.length).toBeGreaterThan(0);
		for (const c of slides) expect(c.options.duration).toBe(1000);
	});
});
