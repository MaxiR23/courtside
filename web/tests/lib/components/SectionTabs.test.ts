// web/tests/lib/components/SectionTabs.test.ts
//
// Tests for the SectionTabs component.
//
// Tested:
// - One link per tab in the given order, pointing at its section
// - The mini score when given, none without it
// - The mini score names a guest without a code by its name
// - A pre-formatted mini text, alone or with tabs
// - Nothing with no tabs and no mini score
// - A click scrolls smoothly to the section, instantly under reduced motion
// - The nav stays above the page content: sticky with z-index from --tabs-z-index
// - The mini score or text is hidden until the watched element has left the top of the viewport, then shown, hidden again on return
// - Stacked on its own row on the mobile layout only; animated, not under reduced motion
// - No watched element yet: the mini stays hidden and no observer is built
//
// What is covered:
// - Each state the tabs show, plus the click
// - A stub section element and a mocked scrollIntoView; no layout in jsdom
// - The stacking rule is read from the component source and tokens.css, since
//   jsdom does not apply scoped styles
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SectionTabs.test.ts
//
// SEE: web/src/lib/components/SectionTabs.svelte
// SEE: web/src/lib/styles/tokens.css
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import SectionTabs from '../../../src/lib/components/SectionTabs.svelte';
import type { SectionTab } from '../../../src/lib/game/types';

const tabs: SectionTab[] = [
	{ id: 'score', label: 'Score' },
	{ id: 'box-score', label: 'Box score' },
	{ id: 'injuries', label: 'Injuries' }
];

const league = (code: string) => ({ code, name: null, city: null, guest: false });
const miniScore = { awayTeam: league('LAL'), away: 63, home: 62, homeTeam: league('GSW') };

function stubSection(id: string) {
	const section = document.createElement('section');
	section.id = id;
	const scrollIntoView = vi.fn();
	section.scrollIntoView = scrollIntoView;
	document.body.append(section);
	return scrollIntoView;
}

function watched(layout: 'desktop' | 'mobile' = 'desktop') {
	const element = document.createElement('div');
	document.body.append(element);
	return { element, layout };
}

afterEach(() => {
	vi.unstubAllGlobals();
	document.body.innerHTML = '';
});

describe('SectionTabs', () => {
	it('renders one link per tab in the given order, pointing at its section', () => {
		render(SectionTabs, { props: { tabs, miniScore: null, reveal: watched() } });
		const links = screen.getAllByRole('link');
		expect(links.map((a) => a.textContent)).toEqual(['Score', 'Box score', 'Injuries']);
		expect(links.map((a) => a.getAttribute('href'))).toEqual(['#score', '#box-score', '#injuries']);
		expect(screen.getByRole('navigation', { name: 'Sections' })).toBeTruthy();
	});

	it('shows the mini score when given', () => {
		const { container } = render(SectionTabs, { props: { tabs, miniScore, reveal: watched() } });
		expect(container.querySelector('.mini-score')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
			'LAL 63 – 62 GSW'
		);
	});

	it('names a guest without a code by its name in the mini score', () => {
		const guest = { code: null, name: 'Mariners', city: 'Harbor City', guest: true };
		const { container } = render(SectionTabs, {
			props: { tabs, miniScore: { ...miniScore, awayTeam: guest }, reveal: watched() }
		});
		expect(container.querySelector('.mini-score')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
			'Mariners 63 – 62 GSW'
		);
	});

	it('shows no mini score without it', () => {
		const { container } = render(SectionTabs, {
			props: { tabs, miniScore: null, reveal: watched() }
		});
		expect(container.querySelector('.mini-score')).toBeNull();
	});

	it('shows a mini text, and renders with only a mini text', () => {
		const { container, unmount } = render(SectionTabs, {
			props: { tabs, mini: 'OKC 57–25', reveal: watched() }
		});
		expect(container.querySelector('.mini-score')?.textContent).toBe('OKC 57–25');
		unmount();
		const only = render(SectionTabs, { props: { tabs: [], mini: 'OKC 57–25', reveal: watched() } });
		expect(only.container.querySelector('nav')).toBeTruthy();
		expect(only.container.querySelector('.mini-score')?.textContent).toBe('OKC 57–25');
	});

	it('renders nothing with no tabs and no mini score', () => {
		const { container } = render(SectionTabs, {
			props: { tabs: [], miniScore: null, reveal: watched() }
		});
		expect(container.querySelector('nav')).toBeNull();
	});

	it('scrolls smoothly to the section on click', async () => {
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const scrollIntoView = stubSection('box-score');
		render(SectionTabs, { props: { tabs, miniScore: null, reveal: watched() } });
		const notPrevented = await fireEvent.click(screen.getByRole('link', { name: 'Box score' }));
		expect(notPrevented).toBe(false);
		expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
	});

	it('scrolls instantly under reduced motion', async () => {
		vi.stubGlobal('matchMedia', (query: string) => ({
			matches: query === '(prefers-reduced-motion: reduce)'
		}));
		const scrollIntoView = stubSection('injuries');
		render(SectionTabs, { props: { tabs, miniScore: null, reveal: watched() } });
		await fireEvent.click(screen.getByRole('link', { name: 'Injuries' }));
		expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'auto', block: 'start' });
	});

	it('does nothing when the section is not on the page yet', async () => {
		render(SectionTabs, { props: { tabs, miniScore: null, reveal: watched() } });
		await expect(fireEvent.click(screen.getByRole('link', { name: 'Score' }))).resolves.toBe(false);
	});

	it('stacks the nav above the page content through the tabs layer token', () => {
		const source = readFileSync(
			join(import.meta.dirname, '../../../src/lib/components/SectionTabs.svelte'),
			'utf8'
		);
		const block = /\.section-tabs\s*\{([^}]*)\}/.exec(source)?.[1] ?? '';
		expect(block).toMatch(/position:\s*sticky;/);
		expect(block).toMatch(/z-index:\s*var\(--tabs-z-index\);/);

		const tokens = readFileSync(
			join(import.meta.dirname, '../../../src/lib/styles/tokens.css'),
			'utf8'
		);
		const level = Number(/--tabs-z-index:\s*(-?\d+);/.exec(tokens)?.[1]);
		expect(level).toBeGreaterThanOrEqual(1);
	});
});

type Entry = { isIntersecting: boolean; boundingClientRect: { top: number } };

function stubObserver() {
	const state = { callbacks: [] as ((entries: Entry[]) => void)[], created: 0 };
	class FakeObserver {
		constructor(callback: (entries: Entry[]) => void) {
			state.created += 1;
			state.callbacks.push(callback);
		}
		observe = vi.fn();
		disconnect = vi.fn();
	}
	vi.stubGlobal('IntersectionObserver', FakeObserver);
	return state;
}

const passed: Entry = { isIntersecting: false, boundingClientRect: { top: -10 } };
const back: Entry = { isIntersecting: true, boundingClientRect: { top: 100 } };

function revealed(
	layout: 'desktop' | 'mobile' = 'desktop',
	score: typeof miniScore | null = miniScore
) {
	return render(SectionTabs, {
		props: { tabs, miniScore: score, reveal: watched(layout) }
	});
}

describe('SectionTabs reveal', () => {
	it('hides the mini score at load when it reveals on scroll', () => {
		stubObserver();
		const { container } = revealed();
		expect(container.querySelector('.mini-score')?.getAttribute('aria-hidden')).toBe('true');
		const nav = container.querySelector('nav');
		expect(nav?.classList.contains('open')).toBe(false);
	});

	it('shows the mini score once the observer reports the watched element out of view', async () => {
		const observer = stubObserver();
		const { container } = revealed();
		await waitFor(() => expect(observer.callbacks).toHaveLength(1));
		observer.callbacks[0]([passed]);
		await tick();
		expect(container.querySelector('.mini-score')?.hasAttribute('aria-hidden')).toBe(false);
		expect(container.querySelector('nav')?.classList.contains('open')).toBe(true);
	});

	it('hides the mini score again when the watched element comes back', async () => {
		const observer = stubObserver();
		const { container } = revealed();
		await waitFor(() => expect(observer.callbacks).toHaveLength(1));
		observer.callbacks[0]([passed]);
		await tick();
		observer.callbacks[0]([back]);
		await tick();
		expect(container.querySelector('.mini-score')?.getAttribute('aria-hidden')).toBe('true');
		expect(container.querySelector('nav')?.classList.contains('open')).toBe(false);
	});

	it('keeps the mini score hidden without IntersectionObserver', async () => {
		vi.stubGlobal('IntersectionObserver', undefined);
		const { container } = revealed();
		await tick();
		expect(container.querySelector('.mini-score')?.getAttribute('aria-hidden')).toBe('true');
	});

	it('stacks the mini score on its own row only on the mobile layout', () => {
		stubObserver();
		const mobile = revealed('mobile');
		expect(mobile.container.querySelector('nav')?.classList.contains('stacked')).toBe(true);
		mobile.unmount();
		const desktop = revealed('desktop');
		expect(desktop.container.querySelector('nav')?.classList.contains('stacked')).toBe(false);
		desktop.unmount();
		const none = revealed('mobile', null);
		expect(none.container.querySelector('nav')?.classList.contains('stacked')).toBe(false);
	});

	it('hides the mini text at load and shows it once the watched element has passed', async () => {
		const observer = stubObserver();
		const { container } = render(SectionTabs, {
			props: { tabs, mini: 'OKC 57–25', reveal: watched() }
		});
		expect(container.querySelector('.mini-score')?.getAttribute('aria-hidden')).toBe('true');
		expect(container.querySelector('nav')?.classList.contains('open')).toBe(false);
		await waitFor(() => expect(observer.callbacks).toHaveLength(1));
		observer.callbacks[0]([passed]);
		await tick();
		expect(container.querySelector('.mini-score')?.hasAttribute('aria-hidden')).toBe(false);
		expect(container.querySelector('nav')?.classList.contains('open')).toBe(true);
		observer.callbacks[0]([back]);
		await tick();
		expect(container.querySelector('.mini-score')?.getAttribute('aria-hidden')).toBe('true');
	});

	it('stacks the mini text on its own row on the mobile layout', () => {
		stubObserver();
		const { container } = render(SectionTabs, {
			props: { tabs, mini: 'OKC 57–25', reveal: watched('mobile') }
		});
		const nav = container.querySelector('nav');
		expect(nav?.classList.contains('stacked')).toBe(true);
		expect(nav?.classList.contains('open')).toBe(false);
	});

	it('keeps the mini hidden and builds no observer while the watched element is null', () => {
		const observer = stubObserver();
		const { container } = render(SectionTabs, {
			props: { tabs, mini: 'OKC 57–25', reveal: { element: null, layout: 'desktop' } }
		});
		expect(observer.created).toBe(0);
		expect(container.querySelector('.mini-score')?.getAttribute('aria-hidden')).toBe('true');
	});

	it.each([
		[false, true],
		[true, false]
	])('animates the change when reduced motion is %s: %s', async (reduced, animates) => {
		const observer = stubObserver();
		const animate = vi.fn(() => ({ cancel: vi.fn() }));
		Object.assign(HTMLElement.prototype, { animate });
		vi.stubGlobal('matchMedia', (query: string) => ({
			matches: reduced && query === '(prefers-reduced-motion: reduce)'
		}));
		revealed();
		await waitFor(() => expect(observer.callbacks).toHaveLength(1));
		observer.callbacks[0]([passed]);
		await tick();
		expect(animate.mock.calls.length > 0).toBe(animates);
		Reflect.deleteProperty(HTMLElement.prototype, 'animate');
	});

	it('keeps the bar height in the flow while the mobile row is open', () => {
		const source = readFileSync(
			join(import.meta.dirname, '../../../src/lib/components/SectionTabs.svelte'),
			'utf8'
		);
		const open = /\.stacked\.open\s*\{([^}]*)\}/.exec(source)?.[1] ?? '';
		expect(open).toMatch(/padding-top:\s*var\(--mini-score-row-height-mobile\);/);
		expect(open).toMatch(/margin-bottom:\s*calc\(-1 \* var\(--mini-score-row-height-mobile\)\);/);
		const hidden = /\.mini-score\s*\{([^}]*)\}/.exec(source)?.[1] ?? '';
		expect(hidden).toMatch(/opacity:\s*0;/);
		expect(hidden).toMatch(/pointer-events:\s*none;/);
	});
});
