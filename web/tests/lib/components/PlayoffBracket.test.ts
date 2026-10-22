// web/tests/lib/components/PlayoffBracket.test.ts
//
// Tests for the PlayoffBracket component.
//
// Tested:
// - Desktop: 15 series buttons placed from the layout, in every state's fixture
// - 14 connectors, in the complete class exactly where the feeder series is complete; every SVG stroke is non-scaling
// - Dashed frames for series with no team, a dashed row for a series with one team
// - The Finals frame in accent and the Champion label only once the Finals is complete
// - A click on a card sets level 2, pressed on "2 Series", and lists its games; no list at level 1
// - Previous, next and the arrow keys inside the bracket move the selection
// - An Esc already taken by another handler (defaultPrevented) does not zoom out
// - Esc and a click on the viewport background go back to level 1; a click on the games list does not
// - A native scroll of the viewport goes back to 0 and pans the camera; the arrow keys move the focus to the selected card
// - The layer's style holds only the transform after every input
// - Reduced motion: no animation
// - A Finals game button draws its focus ring as a non-scaling SVG rect
// - In the Finals games list a selectable game is a button that calls onFinalsGame; any other is not a button
// - Mobile: no controls, 7 rounds in the design order, East round 1 with four cards, a tap opens the sheet, the scrim and Esc close it and return the focus
//
// What is covered:
// - The component with a real camera, element sizes stubbed, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayoffBracket.test.ts
//
// SEE: web/src/lib/components/PlayoffBracket.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import PlayoffBracket from '../../../src/lib/components/PlayoffBracket.svelte';
import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import { SERIES_AT, SERIES_IDS } from '../../../src/lib/playoffs/bracket-layout';

const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;

const FIXTURES = [
	'playoffs-picture.json',
	'playoffs-playin.json',
	'playoffs-bracket.json',
	'playoffs-complete.json'
];

const bracketOf = (name = 'playoffs-bracket.json') =>
	toPlayoffsView(
		JSON.parse(
			readFileSync(join(__dirname, '..', 'feed', 'fixtures', name), 'utf8')
		) as PlayoffsFeed,
		null
	).bracket;

const show = (
	layout: 'desktop' | 'mobile' = 'desktop',
	name = 'playoffs-bracket.json',
	finalsSelectable: string[] = [],
	onFinalsGame = vi.fn()
) =>
	render(PlayoffBracket, {
		props: { bracket: bracketOf(name), layout, gameHref, finalsSelectable, onFinalsGame }
	});

const layerOf = (container: Element) => container.querySelector('.layer') as HTMLElement;
const viewportOf = (container: Element) => container.querySelector('.viewport') as HTMLElement;
const pressed = (name: string) =>
	screen.getByRole('button', { name: new RegExp(`^${name}\\b`) }).getAttribute('aria-pressed');
const styleIsOnlyTransform = (container: Element) =>
	expect(layerOf(container).getAttribute('style')).toMatch(/^transform: [^;]+;?$/);

const reducedMotion = () =>
	vi.stubGlobal('matchMedia', (query: string) => ({
		matches: query === '(prefers-reduced-motion: reduce)'
	}));

beforeEach(() => {
	Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
		configurable: true,
		get: () => 1200
	});
	Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
		configurable: true,
		get: () => 500
	});
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	delete (HTMLElement.prototype as { animate?: unknown }).animate;
	delete (HTMLElement.prototype as { clientWidth?: unknown }).clientWidth;
	delete (HTMLElement.prototype as { clientHeight?: unknown }).clientHeight;
	document.body.style.overflow = '';
});

describe('PlayoffBracket layout', () => {
	it('renders the 15 series as buttons in every state', () => {
		for (const name of FIXTURES) {
			const { container, unmount } = show('desktop', name);
			const buttons = [...container.querySelectorAll('.series')];
			expect(buttons).toHaveLength(15);
			expect(buttons.every((b) => b.tagName === 'BUTTON' && !b.hasAttribute('tabindex'))).toBe(
				true
			);
			unmount();
		}
	});

	it('places the cards from the layout', () => {
		const { container } = show();
		const slots = [...container.querySelectorAll<HTMLElement>('.slot')];
		expect(slots.map((s) => [s.style.left, s.style.top])).toEqual(
			SERIES_IDS.map((id) => [`${SERIES_AT[id].x}px`, `${SERIES_AT[id].y}px`])
		);
	});

	it('draws 14 connectors, accent exactly where the feeder series is complete', () => {
		const { container } = show();
		const lines = [...container.querySelectorAll('.connector')];
		expect(lines).toHaveLength(14);
		expect(lines.filter((l) => l.classList.contains('complete'))).toHaveLength(1);
		const done = show('desktop', 'playoffs-complete.json');
		const completeCount = bracketOf('playoffs-complete.json').series.filter(
			(s) => s.complete && s.id !== 'finals'
		).length;
		expect(done.container.querySelectorAll('.connector.complete')).toHaveLength(completeCount);
	});

	it('draws every SVG stroke non-scaling', () => {
		const { container } = show();
		const strokes = [...container.querySelectorAll('svg path, svg rect')];
		expect(strokes.length).toBeGreaterThan(14);
		expect(strokes.every((s) => s.getAttribute('vector-effect') === 'non-scaling-stroke')).toBe(
			true
		);
	});

	it('dashes the frame of a series with no team and the empty row of one with a single team', () => {
		const series = bracketOf().series;
		const { container } = show();
		expect(container.querySelectorAll('.frame.dashed')).toHaveLength(
			series.filter((s) => s.decided === 'none').length
		);
		expect(container.querySelectorAll('.row-dash')).toHaveLength(
			series.filter((s) => s.decided === 'one').length
		);
	});

	it('draws the Finals frame in accent and the Champion label only once it is complete', () => {
		const open = show();
		expect(open.container.querySelector('.frame.champion')).toBeNull();
		expect(screen.queryByText('Champion')).toBeNull();
		open.unmount();
		const done = show('desktop', 'playoffs-complete.json');
		expect(done.container.querySelectorAll('.frame.champion')).toHaveLength(1);
		expect(screen.getByText('Champion')).toBeTruthy();
	});

	it('is a labelled group', () => {
		show();
		expect(screen.getByRole('group', { name: 'Bracket' })).toBeTruthy();
	});
});

describe('PlayoffBracket levels', () => {
	it('starts at level 1 with no games list, the fit in the layer', () => {
		const { container } = show();
		expect(pressed('1')).toBe('true');
		expect(pressed('2')).toBe('false');
		expect(container.querySelector('.games')).toBeNull();
		expect(layerOf(container).style.transform).toMatch(/^translate\(.+\) scale\(/);
		styleIsOnlyTransform(container);
	});

	it('goes to level 2 on a card click and lists the games of that series', async () => {
		const { container } = show();
		await fireEvent.click(screen.getByRole('button', { name: 'East · Round 1 · QXA · QXH' }));
		expect(pressed('2')).toBe('true');
		expect(pressed('1')).toBe('false');
		expect(container.querySelectorAll('.games .game')).toHaveLength(5);
		expect(screen.getByText('G3 · at QXH')).toBeTruthy();
		styleIsOnlyTransform(container);
	});

	it('goes back to level 1 from the segmented switch and keeps the games list away', async () => {
		const { container } = show();
		await fireEvent.click(screen.getByRole('button', { name: 'East · Round 1 · QXA · QXH' }));
		await fireEvent.click(screen.getByRole('button', { name: /^1\s*Bracket/ }));
		expect(pressed('1')).toBe('true');
		expect(container.querySelector('.games')).toBeNull();
	});

	it('goes to the first series from "2 Series" with nothing selected', async () => {
		const { container } = show();
		await fireEvent.click(screen.getByRole('button', { name: /^2\s*Series/ }));
		expect(pressed('2')).toBe('true');
		expect(container.querySelectorAll('.games .game')).toHaveLength(5);
	});

	it('moves the selection with next and previous', async () => {
		const { container } = show();
		await fireEvent.click(screen.getByRole('button', { name: 'Next series' }));
		expect(container.querySelectorAll('.games .game')).toHaveLength(5);
		await fireEvent.click(screen.getByRole('button', { name: 'Next series' }));
		expect(container.querySelectorAll('.games .game')).toHaveLength(5);
		await fireEvent.click(screen.getByRole('button', { name: 'Next series' }));
		expect(container.querySelectorAll('.games .game')).toHaveLength(1);
		await fireEvent.click(screen.getByRole('button', { name: 'Previous series' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Previous series' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Previous series' }));
		await tick();
		expect(pressed('2')).toBe('true');
		expect(container.querySelectorAll('.games .game')).toHaveLength(0);
	});

	it('moves the selection with the arrow keys while focus is inside the bracket', async () => {
		const { container } = show();
		const control = screen.getByRole('button', { name: /^1\s*Bracket/ });
		control.focus();
		await fireEvent.keyDown(control, { key: 'ArrowRight' });
		expect(container.querySelectorAll('.games .game')).toHaveLength(5);
		await fireEvent.keyDown(control, { key: 'ArrowDown' });
		expect(container.querySelectorAll('.games .game')).toHaveLength(5);
		await fireEvent.keyDown(control, { key: 'ArrowDown' });
		expect(container.querySelectorAll('.games .game')).toHaveLength(1);
		await fireEvent.keyDown(control, { key: 'ArrowLeft' });
		await fireEvent.keyDown(control, { key: 'ArrowUp' });
		await fireEvent.keyDown(control, { key: 'ArrowUp' });
		expect(container.querySelectorAll('.games .game')).toHaveLength(0);
		expect(pressed('2')).toBe('true');
	});

	it('does not take arrow keys pressed outside the bracket', async () => {
		show();
		await fireEvent.keyDown(document.body, { key: 'ArrowRight' });
		expect(pressed('1')).toBe('true');
	});

	it('goes back to level 1 on Esc', async () => {
		show();
		await fireEvent.click(screen.getByRole('button', { name: /^2\s*Series/ }));
		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(pressed('1')).toBe('true');
	});

	it('ignores an Esc another handler already took', async () => {
		show();
		await fireEvent.click(screen.getByRole('button', { name: /^2\s*Series/ }));
		const event = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true });
		event.preventDefault();
		window.dispatchEvent(event);
		await tick();
		expect(pressed('2')).toBe('true');
	});

	it('goes back to level 1 on a click on the viewport background, not on the games list', async () => {
		const { container } = show();
		await fireEvent.click(screen.getByRole('button', { name: /^2\s*Series/ }));
		await fireEvent.click(container.querySelector('.games .game')!);
		expect(pressed('2')).toBe('true');
		await fireEvent.click(viewportOf(container));
		expect(pressed('1')).toBe('true');
	});

	it('keeps level 1 on a click on the viewport background', async () => {
		const { container } = show();
		await fireEvent.click(viewportOf(container));
		expect(pressed('1')).toBe('true');
	});

	it('keeps the layer style as only the transform after every input', async () => {
		const { container } = show();
		await fireEvent.click(screen.getByRole('button', { name: 'Next series' }));
		styleIsOnlyTransform(container);
		await fireEvent.keyDown(window, { key: 'Escape' });
		styleIsOnlyTransform(container);
		await fireEvent.click(screen.getByRole('button', { name: 'Previous series' }));
		styleIsOnlyTransform(container);
	});

	it('absorbs a native scroll of the viewport: back to 0, and the camera pans', async () => {
		const { container } = show();
		const viewport = viewportOf(container);
		const before = layerOf(container).style.transform;
		viewport.scrollLeft = 40;
		await fireEvent.scroll(viewport);
		expect(viewport.scrollLeft).toBe(0);
		expect(layerOf(container).style.transform).not.toBe(before);
		styleIsOnlyTransform(container);
	});

	it('moves the focus to the next and the previous series card with the arrow keys', async () => {
		const { container } = show();
		const cards = () => [...container.querySelectorAll<HTMLButtonElement>('.slot > button')];
		cards()[0].focus();
		await fireEvent.keyDown(cards()[0], { key: 'ArrowRight' });
		expect(document.activeElement).toBe(cards()[0]);
		await fireEvent.keyDown(cards()[0], { key: 'ArrowRight' });
		expect(document.activeElement).toBe(cards()[1]);
		await fireEvent.keyDown(cards()[1], { key: 'ArrowRight' });
		expect(document.activeElement).toBe(cards()[2]);
		await fireEvent.keyDown(cards()[2], { key: 'ArrowLeft' });
		expect(document.activeElement).toBe(cards()[1]);
	});

	it('animates the camera, and does not under reduced motion', async () => {
		const animate = vi.fn(() => ({ cancel: vi.fn() }));
		(HTMLElement.prototype as { animate?: unknown }).animate = animate;
		show();
		await fireEvent.click(screen.getByRole('button', { name: 'Next series' }));
		expect(animate).toHaveBeenCalled();
		animate.mockClear();
		reducedMotion();
		await fireEvent.click(screen.getByRole('button', { name: 'Next series' }));
		expect(animate).not.toHaveBeenCalled();
	});
});

describe('PlayoffBracket Finals games', () => {
	it('makes a selectable Finals game a button that selects it, and leaves the others plain', async () => {
		const onFinalsGame = vi.fn();
		const { container } = show('desktop', 'playoffs-complete.json', ['g101'], onFinalsGame);
		await fireEvent.click(screen.getByRole('button', { name: /NBA Finals/ }));
		const rows = [...container.querySelectorAll('.games .game')];
		expect(rows.length).toBeGreaterThan(1);
		expect(rows[0].querySelector('button')).not.toBeNull();
		expect(rows[1].querySelector('button')).toBeNull();
		await fireEvent.click(rows[0].querySelector('button')!);
		expect(onFinalsGame).toHaveBeenCalledWith('g101');
	});

	it('draws the focus ring of a Finals game button non-scaling, not with the global outline', async () => {
		const { container } = show('desktop', 'playoffs-complete.json', ['g101']);
		await fireEvent.click(screen.getByRole('button', { name: /NBA Finals/ }));
		const button = container.querySelector('.games .game-button')!;
		const rect = button.querySelector('svg.ring rect')!;
		expect(rect.getAttribute('vector-effect')).toBe('non-scaling-stroke');
	});

	it('makes no game button in a series other than the Finals', async () => {
		const { container } = show('desktop', 'playoffs-bracket.json', ['b101']);
		await fireEvent.click(container.querySelectorAll('.series')[0]);
		expect(container.querySelectorAll('.games .game').length).toBeGreaterThan(0);
		expect(container.querySelector('.games button')).toBeNull();
	});
});

describe('PlayoffBracket mobile', () => {
	it('has no zoom controls and no viewport', () => {
		const { container } = show('mobile');
		expect(container.querySelector('.controls')).toBeNull();
		expect(container.querySelector('.viewport')).toBeNull();
		expect(screen.queryByRole('button', { name: /Bracket/ })).toBeNull();
	});

	it('stacks 7 rounds in the design order, East round 1 with four cards', () => {
		const { container } = show('mobile');
		const rounds = [...container.querySelectorAll('.round')];
		expect(rounds.map((r) => r.querySelector('.round-title')?.textContent)).toEqual([
			'East · Round 1',
			'East · Conference semifinals',
			'East · Conference finals',
			'NBA Finals',
			'West · Conference finals',
			'West · Conference semifinals',
			'West · Round 1'
		]);
		expect(rounds[0].querySelectorAll('.series')).toHaveLength(4);
		expect(container.querySelectorAll('.series')).toHaveLength(15);
	});

	it('opens the sheet on a tap, closes it with the scrim and returns the focus to the card', async () => {
		const { container } = show('mobile');
		const card = screen.getByRole('button', { name: 'East · Round 1 · QXD · QXE' });
		await fireEvent.click(card);
		expect(screen.getByRole('dialog', { name: 'East · Round 1' })).toBeTruthy();
		await fireEvent.click(container.ownerDocument.querySelector('.scrim')!);
		expect(screen.queryByRole('dialog')).toBeNull();
		expect(document.activeElement).toBe(card);
	});

	it('closes the sheet with Esc', async () => {
		show('mobile');
		await fireEvent.click(screen.getByRole('button', { name: 'East · Round 1 · QXD · QXE' }));
		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(screen.queryByRole('dialog')).toBeNull();
	});
});
