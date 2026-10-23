// web/tests/lib/components/CupBracketTree.test.ts
//
// Tests for the CupBracketTree component: the Cup bracket under 680px.
//
// Tested:
// - Complete knockout: kicker, H2, conference labels, row labels (only the last in accent), 4/2/1 cards in TREE_ROWS order
// - Every card is a link to the game page when the game has a detail page; the final's card shows codes, scores, the loser, the date
// - The winner line takes the feed's accent, else the neutral accent; the logo or the monogram in the mark
// - No camera: no viewport, no layer, no transform
// - Undecided knockout: 7 buttons, two dashed tiles each, slot label and rule text, To be decided for a seed with no seed, no score, date or winner line
// - Partial states: a scheduled game and a final game without a detail page are buttons
// - A tap on a button calls onOpen with the id and the button; a linked card does not
// - Spanish copy
//
// What is covered:
// - The component from props built with toCupView on the invented Cup feeds, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/CupBracketTree.test.ts
//
// SEE: web/src/lib/components/CupBracketTree.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import CupBracketTree from '../../../src/lib/components/CupBracketTree.svelte';
import type { CupFeed, SlotId } from '../../../src/lib/contract/cup';
import { toCupView } from '../../../src/lib/feed/cup-props';
import { preferLanguages } from '../../prefer-languages';

const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;

const feed = (name: string): CupFeed =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', name), 'utf8')) as CupFeed;

const show = (source: CupFeed, onOpen: (id: SlotId, button: HTMLButtonElement) => void = vi.fn()) =>
	render(CupBracketTree, { props: { bracket: toCupView(source).bracket, gameHref, onOpen } });

const texts = (nodes: Iterable<Element>) => [...nodes].map((n) => n.textContent?.trim());
const finalCard = (container: Element) =>
	[...container.querySelectorAll('.card')].find((c) => c.classList.contains('final'))!;

afterEach(() => {
	vi.restoreAllMocks();
});

describe('CupBracketTree complete knockout', () => {
	it('draws the kicker, the heading and the conference labels', () => {
		const { container } = show(feed('cup-complete.json'));
		expect(container.querySelector('.kicker')?.textContent).toBe('2026 NBA Cup');
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('Knockout rounds');
		expect(texts(container.querySelectorAll('.conferences span'))).toEqual(['East', 'West']);
	});

	it('draws the row labels, the last one in accent, and 4, 2 and 1 cards', () => {
		const { container } = show(feed('cup-complete.json'));
		const labels = [...container.querySelectorAll('.row-label')];
		expect(texts(labels)).toEqual([
			'Quarterfinals',
			'Semifinals · Alderton',
			'Championship · Alderton'
		]);
		expect(labels.map((l) => l.classList.contains('final'))).toEqual([false, false, true]);
		const rows = [...container.querySelectorAll('.row')];
		expect(rows.map((r) => r.querySelectorAll('.card').length)).toEqual([4, 2, 1]);
		const names = [...container.querySelectorAll('.card')].map((c) => c.getAttribute('aria-label'));
		expect(names.map((n) => n?.split(' · ')[0])).toEqual([
			...Array(4).fill('Quarterfinals'),
			...Array(2).fill('Semifinals'),
			'Championship'
		]);
	});

	it('makes every card a link to the game page', () => {
		const { container } = show(feed('cup-complete.json'));
		expect(screen.getAllByRole('link')).toHaveLength(7);
		expect(screen.queryAllByRole('button')).toHaveLength(0);
		expect(finalCard(container).getAttribute('href')).toBe('/game/9100004');
	});

	it('draws the codes, scores, loser and date of the final', () => {
		const { container } = show(feed('cup-complete.json'));
		const card = finalCard(container);
		expect(texts(card.querySelectorAll('.code'))).toEqual(['QXA', 'UXA']);
		expect(texts(card.querySelectorAll('.score'))).toEqual(['124', '120']);
		expect([...card.querySelectorAll('.side')].map((s) => s.classList.contains('loser'))).toEqual([
			false,
			true
		]);
		expect(card.querySelector('.date')?.textContent).toBe('Dec 16');
	});

	it('draws the winner line with the winner accent, else the neutral accent', () => {
		const source = feed('cup-complete.json');
		const plain = show(source);
		const neutral = finalCard(plain.container).querySelector<HTMLElement>('.winner-line')!;
		expect(neutral.style.getPropertyValue('--side-accent')).toBe('var(--identity-neutral-accent)');
		plain.unmount();
		for (const slot of source.bracket) slot.accent = { top: '#123456', bottom: '#654321' };
		const { container } = show(source);
		expect(container.querySelectorAll('.winner-line')).toHaveLength(7);
		const line = finalCard(container).querySelector<HTMLElement>('.winner-line')!;
		expect(line.style.getPropertyValue('--side-accent')).toBe('#123456');
	});

	it('draws the logo in the mark and the monogram for a null logo', () => {
		const source = feed('cup-complete.json');
		const final = source.bracket.find((s) => s.id === 'final')!;
		final.top.team!.logo = {
			light: 'https://example.com/x-light.svg',
			dark: 'https://example.com/x-dark.svg'
		};
		const { container } = show(source);
		const marks = finalCard(container).querySelectorAll('.mark');
		expect(marks[0]!.querySelector('img')?.getAttribute('src')).toBe(
			'https://example.com/x-dark.svg'
		);
		expect(marks[1]!.querySelector('img')).toBeNull();
	});

	it('has no camera: no viewport, no layer and no transform', () => {
		const { container } = show(feed('cup-complete.json'));
		expect(container.querySelector('.viewport')).toBeNull();
		expect(container.querySelector('.layer')).toBeNull();
		expect(container.querySelector('[style*="transform"]')).toBeNull();
	});
});

describe('CupBracketTree undecided knockout', () => {
	it('draws 7 buttons, no link, and two dashed tiles in each', () => {
		const { container } = show(feed('cup.json'));
		expect(screen.getAllByRole('button')).toHaveLength(7);
		expect(screen.queryAllByRole('link')).toHaveLength(0);
		for (const card of container.querySelectorAll('.card')) {
			expect(card.querySelectorAll('.empty-tile')).toHaveLength(2);
		}
	});

	it('writes the slot label over the rule text', () => {
		const { container } = show(feed('cup.json'));
		const card = container.querySelector('.card')!;
		expect(texts(card.querySelectorAll('.slot-label'))).toEqual(['East #1 seed', 'East wild card']);
		expect(card.querySelector('.rule-text')?.textContent).toBe('Best group winner');
	});

	it('writes To be decided for a seed with no seed', () => {
		const source = feed('cup.json');
		const label = source.bracket[0]!.top.label;
		if (label?.key !== 'seed') throw new Error('fixture');
		label.seed = null;
		const { container } = show(source);
		expect(container.querySelector('.slot-label')?.textContent).toBe('To be decided');
	});

	it('draws no score, date or winner line', () => {
		const { container } = show(feed('cup.json'));
		for (const selector of ['.score', '.date', '.winner-line']) {
			expect(container.querySelector(selector)).toBeNull();
		}
	});

	it('writes the row labels without a city', () => {
		const { container } = show(feed('cup.json'));
		expect(texts(container.querySelectorAll('.row-label'))).toEqual([
			'Quarterfinals',
			'Semifinals',
			'Championship'
		]);
	});
});

describe('CupBracketTree partial states', () => {
	it('draws a scheduled game without a detail page as a button with the date and no winner line', () => {
		const source = feed('cup-complete.json');
		const game = source.bracket.find((s) => s.id === 'east-qf-1')!.game!;
		game.detailAvailable = false;
		game.winner = null;
		const { container } = show(source);
		const card = screen.getByRole('button');
		expect(card.querySelector('.date')?.textContent).toBe('Dec 1');
		expect(card.querySelector('.winner-line')).toBeNull();
		expect(container.querySelectorAll('a.card')).toHaveLength(6);
	});

	it('draws a final game without a detail page as a button with a winner line', () => {
		const source = feed('cup-complete.json');
		source.bracket.find((s) => s.id === 'final')!.game!.detailAvailable = false;
		show(source);
		const card = screen.getByRole('button');
		expect(card.querySelector('.winner-line')).not.toBeNull();
	});
});

describe('CupBracketTree tap', () => {
	it('calls onOpen with the id and the button for a card without a detail page', async () => {
		const onOpen = vi.fn();
		const { container } = show(feed('cup.json'), onOpen);
		const button = finalCard(container) as HTMLButtonElement;
		await fireEvent.click(button);
		expect(onOpen).toHaveBeenCalledTimes(1);
		expect(onOpen).toHaveBeenCalledWith('final', button);
	});

	it('does not call onOpen for a linked card', async () => {
		const onOpen = vi.fn();
		show(feed('cup-complete.json'), onOpen);
		const link = screen.getAllByRole('link')[0]!;
		link.addEventListener('click', (event) => event.preventDefault());
		await fireEvent.click(link);
		expect(onOpen).not.toHaveBeenCalled();
	});
});

describe('CupBracketTree in Spanish', () => {
	it('writes the kicker, the heading, the conferences and the city label', () => {
		preferLanguages(['es']);
		const { container } = show(feed('cup-complete.json'));
		expect(container.querySelector('.kicker')?.textContent).toBe('Copa NBA 2026');
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('Fases eliminatorias');
		expect(texts(container.querySelectorAll('.conferences span'))).toEqual(['Este', 'Oeste']);
		expect(texts(container.querySelectorAll('.row-label'))[2]).toBe('Final · Alderton');
	});
});
