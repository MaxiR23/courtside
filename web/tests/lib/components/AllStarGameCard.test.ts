// web/tests/lib/components/AllStarGameCard.test.ts
//
// Tests for the AllStarGameCard component.
//
// Tested:
// - The Championship tag is solid and another round's tag is outlined; no tag without a round
// - Final, Final · OT, the live status with its dot, and the scheduled tip-off
// - The loser row is muted and the winner's sigla has the accent border
// - "To be determined" rows for a team-less Championship
// - aria-pressed follows selected; a click calls onSelect with the game id
// - The mobile class sizes the card for the strip
// - No link for a guest team
//
// What is covered:
// - Each state the card shows, drawn from the recorded feeds
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarGameCard.test.ts
//
// SEE: web/src/lib/components/AllStarGameCard.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import AllStarGameCard from '../../../src/lib/components/AllStarGameCard.svelte';
import { viewOf } from '../all-star/views';

const card = (name: 'live' | 'after', id: string) =>
	viewOf(name).games.find((entry) => entry.id === id)!;

describe('AllStarGameCard', () => {
	it('draws the Championship tag solid and another round outlined', () => {
		const final = render(AllStarGameCard, {
			props: { card: card('after', 'g4'), selected: false, layout: 'desktop', onSelect: () => {} }
		});
		expect(final.container.querySelector('.tag')?.classList.contains('solid')).toBe(true);
		const robin = render(AllStarGameCard, {
			props: { card: card('after', 'g1'), selected: false, layout: 'desktop', onSelect: () => {} }
		});
		expect(robin.container.querySelector('.tag')?.textContent).toBe('Round Robin');
		expect(robin.container.querySelector('.tag')?.classList.contains('solid')).toBe(false);
	});

	it('draws no tag for a game with no round', () => {
		const bare = { ...card('after', 'g1'), round: null };
		const { container } = render(AllStarGameCard, {
			props: { card: bare, selected: false, layout: 'desktop', onSelect: () => {} }
		});
		expect(container.querySelector('.tag')).toBeNull();
	});

	it('shows Final, Final · OT, the live status with a dot, and the tip-off', () => {
		const texts = (name: 'live' | 'after', id: string) => {
			const { container, unmount } = render(AllStarGameCard, {
				props: { card: card(name, id), selected: false, layout: 'desktop', onSelect: () => {} }
			});
			const out = {
				text: container.querySelector('.status-text')?.textContent,
				dot: container.querySelector('.live-dot') !== null
			};
			unmount();
			return out;
		};
		expect(texts('after', 'g1')).toEqual({ text: 'Final', dot: false });
		expect(texts('after', 'g2')).toEqual({ text: 'Final · OT', dot: false });
		expect(texts('live', 's2')).toEqual({ text: 'Live · Q1 · 5:12', dot: true });
		expect(texts('live', 'c1')).toEqual({ text: '8:20 PM', dot: false });
	});

	it('mutes the loser and gives the winner sigla the accent border', () => {
		const { container } = render(AllStarGameCard, {
			props: { card: card('after', 'g1'), selected: false, layout: 'desktop', onSelect: () => {} }
		});
		const rows = [...container.querySelectorAll('.row')];
		expect(rows.map((r) => r.classList.contains('loser'))).toEqual([false, true]);
		expect(rows.map((r) => r.querySelector('.sigla')?.classList.contains('winner'))).toEqual([
			true,
			false
		]);
		expect(rows.map((r) => r.querySelector('.score')?.textContent)).toEqual(['21', '18']);
	});

	it('shows To be determined rows for a team-less Championship', () => {
		const { container } = render(AllStarGameCard, {
			props: { card: card('live', 'c1'), selected: false, layout: 'desktop', onSelect: () => {} }
		});
		expect([...container.querySelectorAll('.name')].map((n) => n.textContent?.trim())).toEqual([
			'To be determined',
			'To be determined'
		]);
		expect(container.querySelector('.label')?.textContent).toBe('To be determined');
	});

	it('never links a guest team', () => {
		const { container } = render(AllStarGameCard, {
			props: { card: card('after', 'g1'), selected: false, layout: 'desktop', onSelect: () => {} }
		});
		expect(container.querySelector('a')).toBeNull();
	});

	it('sets aria-pressed from selected and calls onSelect with the id on a click', async () => {
		const onSelect = vi.fn();
		const { rerender } = render(AllStarGameCard, {
			props: { card: card('after', 'g2'), selected: false, layout: 'desktop', onSelect }
		});
		const button = screen.getByRole('button');
		expect(button.getAttribute('aria-pressed')).toBe('false');
		await fireEvent.click(button);
		expect(onSelect).toHaveBeenCalledWith('g2');
		await rerender({ card: card('after', 'g2'), selected: true, layout: 'desktop', onSelect });
		expect(button.getAttribute('aria-pressed')).toBe('true');
		expect(button.classList.contains('selected')).toBe(true);
	});

	it('adds the mobile class with the mobile layout', () => {
		const { container } = render(AllStarGameCard, {
			props: { card: card('after', 'g1'), selected: false, layout: 'mobile', onSelect: () => {} }
		});
		expect(container.querySelector('button')?.classList.contains('mobile')).toBe(true);
	});
});
