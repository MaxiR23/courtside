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
// - The mini score or text is hidden until the bar is stuck (the empty element right above it has left the top of the viewport), then shown, hidden again when it is not
// - Stacked on its own row on the mobile layout only; animated, not under reduced motion
// - The shared sticky bar state resets when the bar unmounts; no sentinel and no observer without tabs or mini
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
import { stickyBar } from '../../../src/lib/scroll/scrolled-past.svelte';

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

afterEach(() => {
	vi.unstubAllGlobals();
	document.body.innerHTML = '';
});

describe('SectionTabs', () => {
	it('renders one link per tab in the given order, pointing at its section', () => {
		render(SectionTabs, { props: { tabs, miniScore: null, layout: 'desktop' } });
		const links = screen.getAllByRole('link');
		expect(links.map((a) => a.textContent)).toEqual(['Score', 'Box score', 'Injuries']);
		expect(links.map((a) => a.getAttribute('href'))).toEqual(['#score', '#box-score', '#injuries']);
		expect(screen.getByRole('navigation', { name: 'Sections' })).toBeTruthy();
	});

	it('shows the mini score when given', () => {
		const { container } = render(SectionTabs, { props: { tabs, miniScore, layout: 'desktop' } });
		expect(container.querySelector('.mini-score')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
			'LAL 63 – 62 GSW'
		);
	});

	it('names a guest without a code by its name in the mini score', () => {
		const guest = { code: null, name: 'Mariners', city: 'Harbor City', guest: true };
		const { container } = render(SectionTabs, {
			props: { tabs, miniScore: { ...miniScore, awayTeam: guest }, layout: 'desktop' }
		});
		expect(container.querySelector('.mini-score')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
			'Mariners 63 – 62 GSW'
		);
	});

	it('shows no mini score without it', () => {
		const { container } = render(SectionTabs, {
			props: { tabs, miniScore: null, layout: 'desktop' }
		});
		expect(container.querySelector('.mini-score')).toBeNull();
	});

	it('shows a mini text, and renders with only a mini text', () => {
		const { container, unmount } = render(SectionTabs, {
			props: { tabs, mini: 'OKC 57–25', layout: 'desktop' }
		});
		expect(container.querySelector('.mini-score')?.textContent).toBe('OKC 57–25');
		unmount();
		const only = render(SectionTabs, { props: { tabs: [], mini: 'OKC 57–25', layout: 'desktop' } });
		expect(only.container.querySelector('nav')).toBeTruthy();
		expect(only.container.querySelector('.mini-score')?.textContent).toBe('OKC 57–25');
	});

	it('renders nothing with no tabs and no mini score', () => {
		const { container } = render(SectionTabs, {
			props: { tabs: [], miniScore: null, layout: 'desktop' }
		});
		expect(container.querySelector('nav')).toBeNull();
	});

	it('scrolls smoothly to the section on click', async () => {
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const scrollIntoView = stubSection('box-score');
		render(SectionTabs, { props: { tabs, miniScore: null, layout: 'desktop' } });
		const notPrevented = await fireEvent.click(screen.getByRole('link', { name: 'Box score' }));
		expect(notPrevented).toBe(false);
		expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
	});

	it('scrolls instantly under reduced motion', async () => {
		vi.stubGlobal('matchMedia', (query: string) => ({
			matches: query === '(prefers-reduced-motion: reduce)'
		}));
		const scrollIntoView = stubSection('injuries');
		render(SectionTabs, { props: { tabs, miniScore: null, layout: 'desktop' } });
		await fireEvent.click(screen.getByRole('link', { name: 'Injuries' }));
		expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'auto', block: 'start' });
	});

	it('does nothing when the section is not on the page yet', async () => {
		render(SectionTabs, { props: { tabs, miniScore: null, layout: 'desktop' } });
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
	const state = {
		callbacks: [] as ((entries: Entry[]) => void)[],
		observed: [] as Element[],
		created: 0
	};
	class FakeObserver {
		constructor(callback: (entries: Entry[]) => void) {
			state.created += 1;
			state.callbacks.push(callback);
		}
		observe = (node: Element) => {
			state.observed.push(node);
		};
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
		props: { tabs, miniScore: score, layout }
	});
}

describe('SectionTabs stuck bar', () => {
	it('hides the mini score at load, before the bar is stuck', () => {
		stubObserver();
		const { container } = revealed();
		expect(container.querySelector('.mini-score')?.getAttribute('aria-hidden')).toBe('true');
		const nav = container.querySelector('nav');
		expect(nav?.classList.contains('open')).toBe(false);
	});

	it('observes the empty element right above the nav and shows the mini score once it reports the bar stuck', async () => {
		const observer = stubObserver();
		const { container } = revealed();
		await waitFor(() => expect(observer.callbacks).toHaveLength(1));
		const sentinel = container.querySelector('nav')?.previousElementSibling;
		expect(sentinel?.tagName).toBe('DIV');
		expect(sentinel?.children).toHaveLength(0);
		expect(observer.observed[0]).toBe(sentinel);
		observer.callbacks[0]([passed]);
		await tick();
		expect(container.querySelector('.mini-score')?.hasAttribute('aria-hidden')).toBe(false);
		expect(container.querySelector('nav')?.classList.contains('open')).toBe(true);
	});

	it('hides the mini score again when the bar is no longer stuck', async () => {
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

	it('opens only the mini of the bar whose own sentinel is above the viewport', async () => {
		const observer = stubObserver();
		const { container } = render(SectionTabs, {
			props: { tabs, miniScore, layout: 'desktop' }
		});
		const other = render(SectionTabs, { props: { tabs, miniScore, layout: 'desktop' } });
		await waitFor(() => expect(observer.callbacks).toHaveLength(2));
		const minis = () => [
			container.querySelector('.mini-score'),
			other.container.querySelector('.mini-score')
		];
		observer.callbacks[0]([passed]);
		await tick();
		expect(minis()[0]?.hasAttribute('aria-hidden')).toBe(false);
		expect(container.querySelector('nav')?.classList.contains('open')).toBe(true);
		expect(minis()[1]?.getAttribute('aria-hidden')).toBe('true');
		expect(other.container.querySelector('nav')?.classList.contains('open')).toBe(false);
		observer.callbacks[0]([back]);
		observer.callbacks[1]([passed]);
		await tick();
		expect(minis()[0]?.getAttribute('aria-hidden')).toBe('true');
		expect(minis()[1]?.hasAttribute('aria-hidden')).toBe(false);
		expect(other.container.querySelector('nav')?.classList.contains('open')).toBe(true);
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

	it('hides the mini text at load and shows it while the bar is stuck', async () => {
		const observer = stubObserver();
		const { container } = render(SectionTabs, {
			props: { tabs, mini: 'OKC 57–25', layout: 'desktop' }
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
			props: { tabs, mini: 'OKC 57–25', layout: 'mobile' }
		});
		const nav = container.querySelector('nav');
		expect(nav?.classList.contains('stacked')).toBe(true);
		expect(nav?.classList.contains('open')).toBe(false);
	});

	it('renders no sentinel and observes nothing with no tabs and no mini', () => {
		const observer = stubObserver();
		const { container } = render(SectionTabs, {
			props: { tabs: [], miniScore: null, mini: null, layout: 'desktop' }
		});
		expect(container.querySelector('nav')).toBeNull();
		expect(container.querySelector('div')).toBeNull();
		expect(observer.created).toBe(0);
	});

	it('resets the shared state when the bar unmounts', async () => {
		const observer = stubObserver();
		const { unmount } = revealed();
		await waitFor(() => expect(observer.callbacks).toHaveLength(1));
		observer.callbacks[0]([passed]);
		await tick();
		expect(stickyBar.stuck).toBe(true);
		unmount();
		expect(stickyBar.stuck).toBe(false);
		expect(stickyBar.bottom).toBe(0);
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
