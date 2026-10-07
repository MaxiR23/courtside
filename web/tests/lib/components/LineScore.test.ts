// web/tests/lib/components/LineScore.test.ts
//
// Tests for the LineScore component.
//
// Tested:
// - The header and each team's points per quarter and total
// - A dash for quarters not played yet in a live game
// - An OT column for one overtime, and 2OT for a second
// - The header in Spanish with a Spanish browser preference
// - Detail mode: OT1 and OT2 labels, and the team name next to the code
//
// What is covered:
// - Regulation, live and overtime games, plus Spanish
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/LineScore.test.ts
//
// SEE: web/src/lib/components/LineScore.svelte
import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { preferLanguages } from '../../prefer-languages';

import LineScore from '../../../src/lib/components/LineScore.svelte';

afterEach(() => {
	vi.restoreAllMocks();
});

const rows = (container: HTMLElement) =>
	[...container.querySelectorAll('.line')].map((line) =>
		[...line.children].map((cell) => cell.textContent?.trim())
	);

const regulation = {
	away: { code: 'GSW', periods: [28, 26, 24, 34], total: 112 },
	home: { code: 'LAL', periods: [25, 27, 22, 30], total: 104 }
};

describe('LineScore', () => {
	it("shows the header Team 1 2 3 4 T and each team's points per quarter and total", () => {
		const { container } = render(LineScore, { props: regulation });
		expect(rows(container)).toEqual([
			['Team', '1', '2', '3', '4', 'T'],
			['GSW', '28', '26', '24', '34', '112'],
			['LAL', '25', '27', '22', '30', '104']
		]);
	});

	it('shows – for quarters not played yet in a live game', () => {
		const { container } = render(LineScore, {
			props: {
				away: { code: 'GSW', periods: [28, 26], total: 54 },
				home: { code: 'LAL', periods: [25, 27], total: 52 }
			}
		});
		expect(rows(container)[1]).toEqual(['GSW', '28', '26', '–', '–', '54']);
	});

	it('adds an OT column for one overtime and 2OT for a second', () => {
		const one = render(LineScore, {
			props: {
				away: { code: 'GSW', periods: [1, 2, 3, 4, 5], total: 15 },
				home: { code: 'LAL', periods: [1, 2, 3, 4, 6], total: 16 }
			}
		});
		expect(rows(one.container)[0]).toEqual(['Team', '1', '2', '3', '4', 'OT', 'T']);
		one.unmount();
		const two = render(LineScore, {
			props: {
				away: { code: 'GSW', periods: [1, 2, 3, 4, 5, 6], total: 21 },
				home: { code: 'LAL', periods: [1, 2, 3, 4, 6, 7], total: 23 }
			}
		});
		expect(rows(two.container)[0]).toEqual(['Team', '1', '2', '3', '4', 'OT', '2OT', 'T']);
	});

	it('shows the header in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		const { container } = render(LineScore, {
			props: {
				away: { code: 'GSW', periods: [1, 2, 3, 4, 5], total: 15 },
				home: { code: 'LAL', periods: [1, 2, 3, 4, 6], total: 16 }
			}
		});
		expect(rows(container)[0]).toEqual(['Equipo', '1', '2', '3', '4', 'PR', 'T']);
	});

	it('labels overtime columns OT1 and OT2 on the detail page', () => {
		const { container } = render(LineScore, {
			props: {
				detail: true,
				away: { code: 'GSW', periods: [1, 2, 3, 4, 5, 6], total: 21 },
				home: { code: 'LAL', periods: [1, 2, 3, 4, 6, 7], total: 23 }
			}
		});
		expect(rows(container)[0]).toEqual(['Team', '1', '2', '3', '4', 'OT1', 'OT2', 'T']);
	});

	it('shows the team name next to the code on the detail page', () => {
		const { container } = render(LineScore, {
			props: {
				detail: true,
				away: { code: 'GSW', name: 'Warriors', periods: [28], total: 28 },
				home: { code: 'LAL', name: 'Lakers', periods: [25], total: 25 }
			}
		});
		const names = [...container.querySelectorAll('.team-name')].map((e) => e.textContent);
		expect(names).toEqual(['Warriors', 'Lakers']);
		expect(container.querySelector('.line-score')?.classList.contains('detail')).toBe(true);
	});
});
