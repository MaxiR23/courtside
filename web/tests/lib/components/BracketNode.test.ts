// web/tests/lib/components/BracketNode.test.ts
//
// Tests for the BracketNode component.
//
// Tested:
// - Level 1: the code and score of a decided side, the label of an undecided one
// - Level 2: tile, name, meta and score; venue, broadcast and the neutral tag for a semifinal or the final
// - A side whose label is null (a seat with no seed) draws no seed label at level 1 and only the rule at level 2
// - An undecided side at level 2: To be decided, the label and rule, the Currently line only with a projection
// - The winner in ink and the loser muted; the West mirrored
// - A click opens the node with its id; it is a native button, so Enter and Tab work; focus changes are reported
// - Focus is reported as true only when the button matches :focus-visible
// - Spanish copy
//
// What is covered:
// - Each state the node shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/BracketNode.test.ts
//
// SEE: web/src/lib/components/BracketNode.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import BracketNode from '../../../src/lib/components/BracketNode.svelte';
import type { CupFeed } from '../../../src/lib/contract/cup';
import type { BracketNodeView } from '../../../src/lib/cup/types';
import { toCupView } from '../../../src/lib/feed/cup-props';
import { preferLanguages } from '../../prefer-languages';

const load = (name: string): CupFeed =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', name), 'utf8')) as CupFeed;

const node = (id: string, fixture = 'cup.json'): BracketNodeView => {
	const found = toCupView(load(fixture)).bracket.nodes.find((n) => n.id === id);
	if (!found) throw new Error(`no node ${id}`);
	return found;
};

const show = (view: BracketNodeView, level: 1 | 2 = 1, extra: Record<string, unknown> = {}) =>
	render(BracketNode, {
		props: { node: view, level, onOpen: () => {}, onFocusChange: () => {}, ...extra }
	});

afterEach(() => {
	vi.restoreAllMocks();
});

describe('BracketNode level 1', () => {
	it('shows the code and score of each decided side', () => {
		const { container } = show(node('final', 'cup-complete.json'));
		expect(screen.getByText('QXA')).toBeTruthy();
		expect(screen.getByText('UXA')).toBeTruthy();
		expect([...container.querySelectorAll('.score')].map((s) => s.textContent)).toEqual([
			'124',
			'120'
		]);
		expect(container.querySelector('.meta')).toBeNull();
	});

	it('shows the label of an undecided side and no score', () => {
		const { container } = show(node('west-qf-1'));
		expect(screen.getByText('West #1 seed')).toBeTruthy();
		expect(screen.getByText('West wild card')).toBeTruthy();
		expect(container.querySelectorAll('.score')).toHaveLength(0);
	});

	it('names the node for assistive technology by its round and both sides', () => {
		show(node('final', 'cup-complete.json'));
		expect(screen.getByRole('button', { name: 'Championship · Herons · Sailors' })).toBeTruthy();
	});

	it('marks the winner and mutes the loser', () => {
		const { container } = show(node('final', 'cup-complete.json'));
		const sides = [...container.querySelectorAll('.side')];
		expect(sides.map((s) => s.classList.contains('winner'))).toEqual([true, false]);
		expect(sides.map((s) => s.classList.contains('loser'))).toEqual([false, true]);
	});

	it('mirrors the West nodes and not the East ones', () => {
		expect(
			show(node('west-sf', 'cup-complete.json')).container.querySelector('.node.mirrored')
		).not.toBeNull();
		expect(
			show(node('east-sf', 'cup-complete.json')).container.querySelector('.node.mirrored')
		).toBeNull();
	});
});

describe('BracketNode level 2', () => {
	it('shows the name, meta, score, venue, broadcast and the neutral tag of the final', () => {
		show(node('final', 'cup-complete.json'), 2);
		expect(screen.getByText('Herons')).toBeTruthy();
		expect(screen.getByText('#1 seed · East Group A · 4-0')).toBeTruthy();
		expect(screen.getByText('#1 seed · West Group B · 4-0')).toBeTruthy();
		expect(screen.getByText('Harbor Arena')).toBeTruthy();
		expect(screen.getByText('Courtside TV')).toBeTruthy();
		expect(screen.getByText('Neutral site')).toBeTruthy();
		expect(screen.getByText('Dec 16')).toBeTruthy();
	});

	it('shows no neutral tag on a quarterfinal', () => {
		show(node('east-qf-1', 'cup-complete.json'), 2);
		expect(screen.queryByText('Neutral site')).toBeNull();
		expect(screen.getByText('Harbor Arena')).toBeTruthy();
	});

	it('shows To be decided, the label and rule and the Currently line of a projection', () => {
		show(node('east-qf-1'), 2);
		expect(screen.getAllByText('To be decided')).toHaveLength(2);
		expect(screen.getByText('East #1 seed · Best group winner')).toBeTruthy();
		expect(screen.getByText('Currently QXA (4-0)')).toBeTruthy();
	});

	it('shows no Currently line without a projection and no footer without a game', () => {
		const { container } = show(node('west-qf-1'), 2);
		expect(screen.getAllByText('To be decided')).toHaveLength(2);
		expect(screen.queryByText(/Currently/)).toBeNull();
		expect(container.querySelector('.footer')).toBeNull();
	});
});

describe('BracketNode with a seedless side', () => {
	const seedless = (): BracketNodeView => {
		const view = node('west-qf-1');
		return { ...view, top: { ...view.top, label: null } };
	};

	it('draws no seed label at level 1', () => {
		const { container } = show(seedless());
		expect(container.querySelectorAll('.slot-label')).toHaveLength(1);
		expect(screen.getByText('West wild card')).toBeTruthy();
		expect(screen.queryByText(/seed/)).toBeNull();
	});

	it('draws only the rule at level 2', () => {
		const view = seedless();
		show(view, 2);
		expect(screen.getByText(view.top.rule).textContent).toBe(view.top.rule);
	});
});

describe('BracketNode interaction', () => {
	it('is one button that opens the node with its id on a click', async () => {
		const onOpen = vi.fn();
		show(node('final', 'cup-complete.json'), 1, { onOpen });
		const button = screen.getByRole('button');
		await fireEvent.click(button);
		expect(onOpen).toHaveBeenCalledWith('final', button);
	});

	it('is a native button, so Enter opens it and Tab reaches it', () => {
		show(node('east-sf', 'cup-complete.json'));
		const button = screen.getByRole('button');
		expect(button.tagName).toBe('BUTTON');
		expect(button.getAttribute('type')).toBe('button');
		expect(button.getAttribute('tabindex')).toBeNull();
	});

	it('reports focus and blur', () => {
		const onFocusChange = vi.fn();
		show(node('final', 'cup-complete.json'), 1, { onFocusChange });
		const button = screen.getByRole('button');
		// jsdom's focus-visible depends on the events before it: pin it to what a Tab would give.
		vi.spyOn(button, 'matches').mockImplementation((selector) => selector === ':focus-visible');
		button.focus();
		button.blur();
		expect(onFocusChange.mock.calls).toEqual([[true], [false]]);
	});
});

describe('BracketNode focus-visible', () => {
	it('reports false when the focus is not focus-visible', () => {
		const onFocusChange = vi.fn();
		show(node('final', 'cup-complete.json'), 1, { onFocusChange });
		const button = screen.getByRole('button');
		vi.spyOn(button, 'matches').mockImplementation(() => false);
		button.focus();
		expect(onFocusChange.mock.calls).toEqual([[false]]);
	});
});

describe('BracketNode in Spanish', () => {
	it('writes the labels and the neutral tag in Spanish', () => {
		preferLanguages(['es']);
		show(node('east-qf-1'), 2);
		expect(screen.getAllByText('Por decidir')).toHaveLength(2);
		expect(screen.getByText('Este · preclasificado 1 · Mejor ganador de grupo')).toBeTruthy();
		show(node('final', 'cup-complete.json'), 2);
		expect(screen.getByText('Sede neutral')).toBeTruthy();
	});
});
