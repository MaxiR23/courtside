// web/tests/lib/components/AllStarPage.test.ts
//
// Tests for the AllStarPage component.
//
// Tested:
// - Ready per state: the section ids in order, and the footer
// - Loading: the header skeleton and the bones strip
// - Unavailable: the nav row, the title and the unavailable row
// - The MVP box link selects the Championship and scrolls to #games
// - Tapping the live scoreboard on mobile selects the live game and scrolls to #games
// - The live tick runs only in the live state
// - A league logo in the box score; the All-Star sigla boxes hold no image
//
// What is covered:
// - Each state the page shows, drawn from the recorded feeds
// - Fake timers and a scrollIntoView spy; jsdom does not lay out
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarPage.test.ts
//
// SEE: web/src/lib/components/AllStarPage.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { AllStarPageState } from '../../../src/lib/all-star/types';
import AllStarPage from '../../../src/lib/components/AllStarPage.svelte';
import { playerHref, teamHref, viewOf } from '../all-star/views';

const UNAVAILABLE = "Data isn't available right now. Check back later.";

const show = (state: AllStarPageState, layout: 'desktop' | 'mobile' = 'desktop') =>
	render(AllStarPage, {
		props: {
			state,
			allGamesHref: '/' as ResolvedPathname,
			standingsHref: '/standings' as ResolvedPathname,
			layout,
			teamHref,
			playerHref
		}
	});
const ready = (name: 'before' | 'live' | 'after'): AllStarPageState => ({
	kind: 'ready',
	view: viewOf(name)
});
const ids = (container: HTMLElement) =>
	[...container.querySelectorAll('.sections > section')].map((s) => s.id);

beforeEach(() => {
	vi.useFakeTimers();
	vi.stubGlobal(
		'matchMedia',
		vi.fn(() => ({ matches: true, addEventListener: () => {}, removeEventListener: () => {} }))
	);
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
	document.body.innerHTML = '';
});

describe('AllStarPage', () => {
	it('draws the sections of each state in order, and the footer', () => {
		for (const [name, expected] of [
			['before', ['last-time']],
			['live', ['games', 'teams']],
			['after', ['mvp', 'games', 'teams']]
		] as const) {
			const { container, unmount } = show(ready(name));
			expect(ids(container)).toEqual(expected);
			expect(container.ownerDocument.querySelector('footer')).toBeTruthy();
			unmount();
		}
	});

	it('draws the Last time section with its heading and link', () => {
		show(ready('before'));
		expect(screen.getByRole('heading', { level: 2, name: 'Last time' })).toBeTruthy();
		expect(screen.getByRole('link', { name: /Every game, box score/ })).toBeTruthy();
	});

	it('draws the teams section with its heading', () => {
		show(ready('after'));
		expect(screen.getByRole('heading', { level: 2, name: 'Teams' })).toBeTruthy();
	});

	it('draws every frame with the All-Star corner marks', () => {
		const { container } = show({ kind: 'loading' });
		const frames = container.querySelectorAll('.blueprint-frame');
		expect(frames.length).toBeGreaterThan(0);
		for (const frame of frames) expect(frame.classList.contains('marks-allstar')).toBe(true);
	});

	it('shows the header skeleton and the bones strip while loading', () => {
		const { container } = show({ kind: 'loading' });
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelectorAll('.card-bones .bone')).toHaveLength(4);
		expect(container.querySelector('section[aria-busy=true]')).not.toBeNull();
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	it('shows the nav, the title and the unavailable row when unavailable', async () => {
		const { container } = show({ kind: 'unavailable' });
		expect(screen.getByRole('heading', { level: 1, name: 'All-Star' })).toBeTruthy();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		expect(screen.getByRole('link', { name: 'All-Star' }).getAttribute('aria-current')).toBe(
			'page'
		);
		expect(container.ownerDocument.querySelector('footer')).toBeTruthy();
	});

	it('selects the Championship and scrolls to #games from the MVP box link', async () => {
		const scrolled: string[] = [];
		Element.prototype.scrollIntoView = vi.fn(function (this: Element) {
			scrolled.push(this.id);
		});
		const { container } = show(ready('after'));
		const cards = () =>
			[...container.querySelectorAll('.game-card')].map((c) => c.getAttribute('aria-pressed'));
		await fireEvent.click(container.querySelectorAll('.game-card')[0]);
		expect(cards()).toEqual(['true', 'false', 'false', 'false']);
		await fireEvent.click(screen.getByRole('button', { name: 'Box score and highlights →' }));
		expect(cards()).toEqual(['false', 'false', 'false', 'true']);
		expect(scrolled).toEqual(['games']);
		expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
			behavior: 'auto',
			block: 'start'
		});
	});

	it('selects the live game and scrolls to #games from the mobile live scoreboard', async () => {
		const scrolled: string[] = [];
		Element.prototype.scrollIntoView = vi.fn(function (this: Element) {
			scrolled.push(this.id);
		});
		const { container } = show(ready('live'), 'mobile');
		await fireEvent.click(container.querySelectorAll('.game-card')[0]);
		await fireEvent.click(container.querySelector('button.live-block')!);
		expect(
			[...container.querySelectorAll('.game-card')].map((c) => c.getAttribute('aria-pressed'))
		).toEqual(['false', 'true', 'false']);
		expect(scrolled).toEqual(['games']);
	});

	it('starts the live tick only in the live state', async () => {
		const timers = vi.spyOn(globalThis, 'setInterval');
		const idle = show(ready('after'));
		await vi.advanceTimersByTimeAsync(0);
		expect(timers).not.toHaveBeenCalled();
		idle.unmount();
		const live = show(ready('live'));
		await vi.advanceTimersByTimeAsync(0);
		expect(timers).toHaveBeenCalledTimes(1);
		expect(timers.mock.calls[0][1]).toBe(1000);
		live.unmount();
	});

	it('uses the mobile classes on mobile', () => {
		const { container } = show(ready('after'), 'mobile');
		expect(container.querySelector('.sections')?.classList.contains('mobile')).toBe(true);
		expect(container.querySelector('.sections .all-star-games.mobile .cards')).not.toBeNull();
		expect(container.querySelector('.nav.sticky')).not.toBeNull();
	});
});

describe('AllStarPage team logos', () => {
	it('draws a league logo in the box score and keeps the sigla boxes free of images', () => {
		const view = structuredClone(viewOf('after'));
		for (const box of Object.values(view.boxes)) {
			for (const row of [...(box?.away.rows ?? []), ...(box?.home.rows ?? [])]) {
				if (row.league) {
					row.league.team.logo = {
						light: 'https://example.com/a-light.svg',
						dark: 'https://example.com/a-dark.svg'
					};
				}
			}
		}
		const { container } = show({ kind: 'ready', view });
		const logos = [...container.querySelectorAll('.team-monogram.allstar-league img')];
		expect(logos.length).toBeGreaterThan(0);
		expect(logos[0]!.getAttribute('src')).toBe('https://example.com/a-dark.svg');
		expect(container.querySelectorAll('.sigla img')).toHaveLength(0);
	});
});
