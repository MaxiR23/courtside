// web/tests/lib/components/SeriesGameLine.test.ts
//
// Tests for the SeriesGameLine component.
//
// Tested:
// - A final game: the label, both codes and scores, the loser muted
// - An overtime game shows OT; a regulation game does not
// - A game that is not final shows its date and venue and no score
//
// What is covered:
// - Each state of the line, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SeriesGameLine.test.ts
//
// SEE: web/src/lib/components/SeriesGameLine.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import SeriesGameLine from '../../../src/lib/components/SeriesGameLine.svelte';
import type { SeriesGameRowView } from '../../../src/lib/playoffs/types';

const game = (change: Partial<SeriesGameRowView> = {}): SeriesGameRowView => ({
	gameId: 'g1',
	linked: true,
	key: 'g1',
	label: 'G1 · at QXH',
	away: { code: 'QXH', score: '98', loser: true },
	home: { code: 'QXA', score: '105', loser: false },
	final: true,
	overtime: false,
	when: null,
	...change
});

describe('SeriesGameLine', () => {
	it('shows the label, both codes and both scores of a final game', () => {
		const { container } = render(SeriesGameLine, { props: { game: game() } });
		expect(screen.getByText('G1 · at QXH')).toBeTruthy();
		expect(container.querySelector('.result')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
			'QXH 98 – 105 QXA'
		);
	});

	it('mutes the losing side only', () => {
		const { container } = render(SeriesGameLine, { props: { game: game() } });
		const sides = [...container.querySelectorAll('.side')];
		expect(sides.map((side) => side.classList.contains('loser'))).toEqual([true, false]);
	});

	it('shows OT in the accent class for an overtime game', () => {
		const { container } = render(SeriesGameLine, { props: { game: game({ overtime: true }) } });
		expect(container.querySelector('.overtime')?.textContent).toBe('OT');
	});

	it('shows no OT for a regulation game', () => {
		const { container } = render(SeriesGameLine, { props: { game: game() } });
		expect(container.querySelector('.overtime')).toBeNull();
	});

	it('shows the date and venue and no score when the game is not final', () => {
		const { container } = render(SeriesGameLine, {
			props: {
				game: game({
					final: false,
					when: 'Apr 28 · Example Arena',
					away: { code: 'QXE', score: '—', loser: false },
					home: { code: 'QXD', score: '—', loser: false }
				})
			}
		});
		expect(screen.getByText('Apr 28 · Example Arena')).toBeTruthy();
		expect(container.querySelector('.result')).toBeNull();
	});
});
