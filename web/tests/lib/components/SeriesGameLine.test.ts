// web/tests/lib/components/SeriesGameLine.test.ts
//
// Tests for the SeriesGameLine component.
//
// Tested:
// - A final game: the number, "at" the home team, the winner's code and score, and the winner's logo
// - The OT tag in the accent class for an overtime game ("OT", "2OT"); none in regulation
// - A game that is not final shows its date and venue and no score
// - The bottom rule takes the winner's resolved color from the feed, else the neutral accent
//
// What is covered:
// - Each state of the cell, drawn from props with no fetch
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
	number: 'G1',
	at: 'at QXH',
	overtimeTag: null,
	winner: {
		team: { code: 'QXA', name: 'Owls', city: 'Summit', guest: false },
		code: 'QXA',
		score: '105–98'
	},
	accent: null,
	away: { code: 'QXA', score: '105', loser: false },
	home: { code: 'QXH', score: '98', loser: true },
	final: true,
	overtime: false,
	when: null,
	...change
});

describe('SeriesGameLine', () => {
	it('shows the number, the home team, the winner code and its score of a final game', () => {
		const { container } = render(SeriesGameLine, { props: { game: game() } });
		expect(screen.getByText('G1')).toBeTruthy();
		expect(screen.getByText('at QXH')).toBeTruthy();
		expect(container.querySelector('.score')?.textContent).toBe('QXA 105–98');
	});

	it('draws the winner logo', () => {
		const logo = {
			light: 'https://example.com/a-light.svg',
			dark: 'https://example.com/a-dark.svg'
		};
		const { container } = render(SeriesGameLine, {
			props: {
				game: game({
					winner: {
						team: { code: 'QXA', name: 'Owls', city: 'Summit', guest: false, logo },
						code: 'QXA',
						score: '105–98'
					}
				})
			}
		});
		expect(container.querySelector('.mark img')?.getAttribute('src')).toBe(
			'https://example.com/a-dark.svg'
		);
	});

	it('shows OT and 2OT in the accent class, and nothing in regulation', () => {
		const ot = render(SeriesGameLine, { props: { game: game({ overtimeTag: 'OT' }) } });
		expect(ot.container.querySelector('.overtime')?.textContent).toBe('OT');
		ot.unmount();
		const two = render(SeriesGameLine, { props: { game: game({ overtimeTag: '2OT' }) } });
		expect(two.container.querySelector('.overtime')?.textContent).toBe('2OT');
		two.unmount();
		const none = render(SeriesGameLine, { props: { game: game() } });
		expect(none.container.querySelector('.overtime')).toBeNull();
	});

	it('shows the date and venue and no score when the game is not final', () => {
		const { container } = render(SeriesGameLine, {
			props: {
				game: game({ final: false, winner: null, when: 'Apr 28 · Example Arena' })
			}
		});
		expect(screen.getByText('Apr 28 · Example Arena')).toBeTruthy();
		expect(container.querySelector('.result')).toBeNull();
		expect(container.querySelector('.rule')).toBeNull();
	});

	it("draws the rule in the winner's color, else the neutral accent", () => {
		const colored = render(SeriesGameLine, { props: { game: game({ accent: '#112233' }) } });
		const rule = colored.container.querySelector<HTMLElement>('.rule')!;
		expect(rule.style.getPropertyValue('--side-accent')).toBe('#112233');
		colored.unmount();
		const neutral = render(SeriesGameLine, { props: { game: game() } });
		expect(
			neutral.container.querySelector<HTMLElement>('.rule')!.style.getPropertyValue('--side-accent')
		).toBe('var(--identity-neutral-accent)');
	});
});
