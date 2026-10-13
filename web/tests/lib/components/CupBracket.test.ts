// web/tests/lib/components/CupBracket.test.ts
//
// Tests for the CupBracket component.
//
// Tested:
// - 7 node buttons reachable by Tab, positioned from the layout, on desktop and on a phone
// - 6 connectors, in the accent class exactly where the feed says the side is known; every stroke is non-scaling; the final's frame in accent
// - Level 1 content at fit and level 2 content after the level switcher
// - The level switcher and the + / - / Fit buttons change the layer's transform and aria-pressed
// - Ctrl+wheel zooms; a vertical wheel at fit is left to the page
// - A drag of 10px pans and the click that ends it opens nothing; a 3px drag then a click opens the node
// - The layer's style holds only the transform after every input
// - Reduced motion: Fit does not animate and lands at once
// - Mobile: no controls and no hint, the wheel ignored, a tap opens the sheet
// - A native scroll of the viewport (focus scrolling it) is absorbed: scrollLeft goes back to 0 and the layer moves by the same amount
// - Closing the panel returns the focus without scrolling
// - Keyboard: Tab to a node, Esc closes the player card only, Esc again closes the panel and returns the focus to the node
//
// What is covered:
// - The component with a real camera and matchup store, element sizes stubbed, no network (the loader is a mock)
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/CupBracket.test.ts
//
// SEE: web/src/lib/components/CupBracket.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

import CupBracket from '../../../src/lib/components/CupBracket.svelte';
import type { CupFeed, SlotId } from '../../../src/lib/contract/cup';
import type { CupMatchupFeed } from '../../../src/lib/contract/cup-matchup';
import { CupMatchupStore } from '../../../src/lib/cup/matchup.svelte';
import { toCupView } from '../../../src/lib/feed/cup-props';

const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;
const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;

const fixture = <T>(name: string): T =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', name), 'utf8')) as T;

const bracketOf = (name = 'cup-complete.json') => toCupView(fixture<CupFeed>(name)).bracket;

let matchup: CupMatchupStore;
let load: Mock<(id: SlotId) => Promise<CupMatchupFeed>>;

const show = (layout: 'desktop' | 'mobile' = 'desktop', name = 'cup-complete.json') =>
	render(CupBracket, {
		props: { bracket: bracketOf(name), layout, matchup, gameHref, playerHref }
	});

const layerOf = (container: Element) => container.querySelector('.layer') as HTMLElement;
const viewportOf = (container: Element) => container.querySelector('.viewport') as HTMLElement;
const nodeButton = (name: RegExp) => screen.getByRole('button', { name });
const pressed = (name: string) =>
	screen.getByRole('button', { name: new RegExp(name) }).getAttribute('aria-pressed');

async function settle() {
	await tick();
	await Promise.resolve();
	await tick();
}

beforeEach(() => {
	Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
		configurable: true,
		get: () => 1200
	});
	Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
		configurable: true,
		get: () => 500
	});
	load = vi.fn((id: SlotId) => {
		void id;
		return Promise.resolve(fixture<CupMatchupFeed>('cup-matchup.json'));
	});
	matchup = new CupMatchupStore(load);
});

afterEach(() => {
	matchup.close();
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	delete (HTMLElement.prototype as { animate?: unknown }).animate;
	delete (HTMLElement.prototype as { clientWidth?: unknown }).clientWidth;
	delete (HTMLElement.prototype as { clientHeight?: unknown }).clientHeight;
	document.body.style.overflow = '';
});

describe('CupBracket layout', () => {
	it('renders the 7 nodes as buttons reachable by Tab', () => {
		const { container } = show();
		const buttons = [...container.querySelectorAll('.node')];
		expect(buttons).toHaveLength(7);
		expect(buttons.every((b) => b.tagName === 'BUTTON' && !b.hasAttribute('tabindex'))).toBe(true);
	});

	it('places the nodes from the desktop layout', () => {
		const { container } = show();
		const slots = [...container.querySelectorAll<HTMLElement>('.slot')];
		expect(slots.map((s) => [s.style.left, s.style.top])).toEqual([
			['0px', '0px'],
			['0px', '760px'],
			['1300px', '380px'],
			['2600px', '380px'],
			['3900px', '380px'],
			['5200px', '0px'],
			['5200px', '760px']
		]);
	});

	it('places the nodes from the mobile layout', () => {
		const { container } = show('mobile');
		const slots = [...container.querySelectorAll<HTMLElement>('.slot')];
		expect(slots.map((s) => [s.style.left, s.style.top])).toEqual([
			['0px', '0px'],
			['1300px', '0px'],
			['650px', '760px'],
			['650px', '1520px'],
			['650px', '2280px'],
			['0px', '3040px'],
			['1300px', '3040px']
		]);
	});

	it('draws 6 connectors, all in the accent class when every side is known', () => {
		const { container } = show();
		const paths = container.querySelectorAll('.connector');
		expect(paths).toHaveLength(6);
		expect([...paths].every((p) => p.classList.contains('known'))).toBe(true);
	});

	it('draws no connector in the accent class when no side is known', () => {
		const { container } = show('desktop', 'cup.json');
		expect(container.querySelectorAll('.connector')).toHaveLength(6);
		expect(container.querySelectorAll('.connector.known')).toHaveLength(0);
	});

	it('keeps every stroke non-scaling and the final frame alone in accent', () => {
		const { container } = show();
		const strokes = container.querySelectorAll('svg path, svg rect');
		expect(strokes.length).toBeGreaterThan(0);
		expect(
			[...strokes].every((s) => s.getAttribute('vector-effect') === 'non-scaling-stroke')
		).toBe(true);
		expect(container.querySelectorAll('rect.frame')).toHaveLength(7);
		expect(container.querySelectorAll('rect.frame.final')).toHaveLength(1);
		expect(container.querySelectorAll('.tick')).toHaveLength(28);
	});
});

describe('CupBracket levels and controls', () => {
	it('shows level 1 at fit, with the round labels and the champion', () => {
		const { container } = show();
		expect(container.querySelectorAll('.code').length).toBeGreaterThan(0);
		expect(container.querySelector('.name')).toBeNull();
		expect(pressed('Bracket')).toBe('true');
		expect(pressed('Round')).toBe('false');
		expect(
			[...container.querySelectorAll('.round-label')].map((l) => l.textContent?.trim())
		).toEqual(['Quarterfinals', 'Semifinals', 'Championship', 'Semifinals', 'Quarterfinals']);
		expect(container.querySelector('.champion')?.textContent).toContain('Herons');
	});

	it('shows level 2 after the level switcher, with no round labels', async () => {
		const { container } = show();
		const before = layerOf(container).style.transform;
		await fireEvent.click(screen.getByRole('button', { name: /Round/ }));
		await tick();
		expect(pressed('Round')).toBe('true');
		expect(pressed('Bracket')).toBe('false');
		expect(container.querySelector('.name')).not.toBeNull();
		expect(container.querySelector('.round-label')).toBeNull();
		expect(layerOf(container).style.transform).not.toBe(before);
		await fireEvent.click(screen.getByRole('button', { name: /Bracket/ }));
		await tick();
		expect(pressed('Bracket')).toBe('true');
		expect(layerOf(container).style.transform).toBe(before);
	});

	it('zooms with + and -, and fits again with Fit', async () => {
		const { container } = show();
		const fit = layerOf(container).style.transform;
		await fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }));
		const zoomed = layerOf(container).style.transform;
		expect(zoomed).not.toBe(fit);
		await fireEvent.click(screen.getByRole('button', { name: 'Zoom out' }));
		expect(layerOf(container).style.transform).not.toBe(zoomed);
		await fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Fit' }));
		expect(layerOf(container).style.transform).toBe(fit);
	});

	it('zooms on ctrl+wheel', () => {
		const { container } = show();
		const before = layerOf(container).style.transform;
		const event = new WheelEvent('wheel', {
			deltaY: -300,
			ctrlKey: true,
			clientX: 400,
			clientY: 200,
			bubbles: true,
			cancelable: true
		});
		viewportOf(container).dispatchEvent(event);
		expect(event.defaultPrevented).toBe(true);
		expect(layerOf(container).style.transform).not.toBe(before);
	});

	it('leaves a vertical wheel at fit to the page', () => {
		const { container } = show();
		const before = layerOf(container).style.transform;
		const event = new WheelEvent('wheel', {
			deltaY: 120,
			bubbles: true,
			cancelable: true
		});
		viewportOf(container).dispatchEvent(event);
		expect(event.defaultPrevented).toBe(false);
		expect(layerOf(container).style.transform).toBe(before);
	});

	it('writes only the transform on the layer after every input', async () => {
		const { container } = show();
		await fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }));
		await fireEvent.click(screen.getByRole('button', { name: /Round/ }));
		viewportOf(container).dispatchEvent(
			new WheelEvent('wheel', { deltaY: -100, ctrlKey: true, bubbles: true, cancelable: true })
		);
		await fireEvent.click(screen.getByRole('button', { name: 'Fit' }));
		expect(layerOf(container).getAttribute('style')).toMatch(/^transform: [^;]+;?$/);
	});
});

describe('CupBracket drag', () => {
	const drag = async (button: Element, distance: number) => {
		await fireEvent.pointerDown(button, { clientX: 100, clientY: 100, pointerId: 1, button: 0 });
		await fireEvent.pointerMove(button, { clientX: 100 + distance, clientY: 100, pointerId: 1 });
		await fireEvent.pointerUp(button, { clientX: 100 + distance, clientY: 100, pointerId: 1 });
	};

	it('pans on a drag of 10px and the click that ends it opens nothing', async () => {
		const open = vi.spyOn(matchup, 'open');
		const { container } = show();
		const before = layerOf(container).style.transform;
		const button = nodeButton(/^Championship ·/);
		await drag(button, 10);
		expect(layerOf(container).style.transform).not.toBe(before);
		await fireEvent.click(button);
		expect(open).not.toHaveBeenCalled();
		expect(layerOf(container).getAttribute('style')).toMatch(/^transform: [^;]+;?$/);
	});

	it('does not pan on a drag of 3px and the click opens the node', async () => {
		const open = vi.spyOn(matchup, 'open');
		const { container } = show();
		const before = layerOf(container).style.transform;
		const button = nodeButton(/^Championship ·/);
		await drag(button, 3);
		await fireEvent.click(button);
		expect(layerOf(container).style.transform).toBe(before);
		expect(open).toHaveBeenCalledWith('final');
	});
});

describe('CupBracket reduced motion', () => {
	it('lands at once on Fit without animating', async () => {
		vi.stubGlobal('matchMedia', (query: string) => ({
			matches: query === '(prefers-reduced-motion: reduce)',
			addEventListener: () => {},
			removeEventListener: () => {}
		}));
		const animate = vi.fn();
		(HTMLElement.prototype as { animate?: unknown }).animate = animate;
		const { container } = show();
		const fit = layerOf(container).style.transform;
		await fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Fit' }));
		expect(animate).not.toHaveBeenCalled();
		expect(layerOf(container).style.transform).toBe(fit);
	});

	it('animates the fly when motion is allowed', async () => {
		const animation = { cancel: vi.fn(), onfinish: null, oncancel: null };
		const animate = vi.fn(() => animation);
		(HTMLElement.prototype as { animate?: unknown }).animate = animate;
		show();
		await fireEvent.click(screen.getByRole('button', { name: 'Fit' }));
		expect(animate).toHaveBeenCalledTimes(1);
	});
});

describe('CupBracket on a phone', () => {
	it('has no controls and no hint', () => {
		const { container } = show('mobile');
		expect(container.querySelector('.controls')).toBeNull();
		expect(screen.queryByText('Scroll to zoom, drag to pan')).toBeNull();
		expect(screen.queryByRole('button', { name: 'Zoom in' })).toBeNull();
	});

	it('ignores the wheel and stays at level 1', () => {
		const { container } = show('mobile');
		const before = layerOf(container).style.transform;
		const event = new WheelEvent('wheel', {
			deltaY: -300,
			ctrlKey: true,
			bubbles: true,
			cancelable: true
		});
		viewportOf(container).dispatchEvent(event);
		expect(event.defaultPrevented).toBe(false);
		expect(layerOf(container).style.transform).toBe(before);
		expect(container.querySelectorAll('.code').length).toBeGreaterThan(0);
	});

	it('opens the sheet on a tap', async () => {
		show('mobile');
		await fireEvent.click(nodeButton(/^Championship ·/));
		await settle();
		const sheet = screen.getByRole('dialog', { name: 'Championship' });
		expect(sheet.getAttribute('aria-modal')).toBe('true');
		expect(load).toHaveBeenCalledWith('final');
	});
});

describe('CupBracket keyboard', () => {
	it('opens the panel from a node, closes the card first on Esc, then the panel, and returns the focus', async () => {
		show();
		const button = nodeButton(/^Championship ·/);
		button.focus();
		expect(document.activeElement).toBe(button);
		await fireEvent.click(button);
		await settle();
		expect(screen.getByRole('dialog', { name: 'Championship' })).toBeTruthy();

		await fireEvent.click(screen.getByRole('button', { name: 'Ari Vance' }));
		expect(screen.getByRole('dialog', { name: 'Ari Vance' })).toBeTruthy();

		await fireEvent.keyDown(window, { key: 'Escape' });
		await tick();
		expect(screen.queryByRole('dialog', { name: 'Ari Vance' })).toBeNull();
		expect(screen.getByRole('dialog', { name: 'Championship' })).toBeTruthy();

		await fireEvent.keyDown(window, { key: 'Escape' });
		await tick();
		expect(screen.queryByRole('dialog')).toBeNull();
		expect(document.activeElement).toBe(button);
	});

	it('returns the focus to the node without scrolling', async () => {
		show();
		const button = nodeButton(/^Championship ·/);
		await fireEvent.click(button);
		await settle();
		const focus = vi.spyOn(button, 'focus');
		await fireEvent.keyDown(window, { key: 'Escape' });
		await tick();
		expect(focus).toHaveBeenCalledWith({ preventScroll: true });
	});

	it('absorbs a native scroll of the viewport into the camera', async () => {
		const { container } = show();
		await fireEvent.click(screen.getByRole('button', { name: /Round/ }));
		await tick();
		const x = () => Number(/translate\((-?[\d.]+)px/.exec(layerOf(container).style.transform)?.[1]);
		const before = x();
		const viewport = viewportOf(container);
		let left = 0;
		Object.defineProperty(viewport, 'scrollLeft', {
			configurable: true,
			get: () => left,
			set: (value: number) => {
				left = value;
			}
		});
		left = 120;
		await fireEvent.scroll(viewport);
		expect(left).toBe(0);
		expect(x()).toBeCloseTo(before - 120, 5);
	});

	it('does nothing on Esc when no panel is open', async () => {
		show();
		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('shows the unavailable line in the panel when the matchup fails, the bracket staying', async () => {
		load.mockRejectedValue(new Error('503'));
		const { container } = show();
		await fireEvent.click(nodeButton(/^Championship ·/));
		await settle();
		expect(screen.getByRole('dialog').textContent).toContain("Data isn't available right now.");
		expect(container.querySelectorAll('.node')).toHaveLength(7);
	});
});
