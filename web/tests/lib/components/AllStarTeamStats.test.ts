// web/tests/lib/components/AllStarTeamStats.test.ts
//
// Tests for the AllStarTeamStats component.
//
// Tested:
// - The six labels in order with both values
// - The better side of each stat comes from the view: the value is ink and the bar accent; a tie has none
// - The bar widths follow the shares of the view
//
// What is covered:
// - Each state a row shows, drawn from the recorded feeds
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarTeamStats.test.ts
//
// SEE: web/src/lib/components/AllStarTeamStats.svelte
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import AllStarTeamStats from '../../../src/lib/components/AllStarTeamStats.svelte';
import { viewOf } from '../all-star/views';

const stats = () => viewOf('after').details.g4.teamStats!;

describe('AllStarTeamStats', () => {
	it('shows the six labels with both values', () => {
		const { container } = render(AllStarTeamStats, { props: { stats: stats() } });
		expect([...container.querySelectorAll('.label')].map((l) => l.textContent)).toEqual([
			'FG%',
			'3PM',
			'Rebounds',
			'Assists',
			'Steals',
			'Blocks'
		]);
		const first = container.querySelector('.stat')!;
		expect(first.querySelector('.value.away')?.textContent).toBe('50.0%');
		expect(first.querySelector('.value.home')?.textContent).toBe('40.0%');
	});

	it('marks the better side from the view, and none on a tie', () => {
		const { container } = render(AllStarTeamStats, { props: { stats: stats() } });
		const rows = [...container.querySelectorAll('.stat')];
		const better = (row: Element) =>
			[...row.querySelectorAll('.value')].map((v) => v.classList.contains('better'));
		expect(better(rows[0])).toEqual([true, false]); // FG%: away
		expect(better(rows[5])).toEqual([false, true]); // blocks: home
		expect(better(rows[4])).toEqual([false, false]); // steals: tie
		const fills = [...rows[0].querySelectorAll('.fill')];
		expect(fills.map((f) => f.classList.contains('better'))).toEqual([true, false]);
	});

	it('sizes each bar by the share of the view', () => {
		const { container } = render(AllStarTeamStats, { props: { stats: stats() } });
		const blocks = [...container.querySelectorAll('.stat')][5];
		const widths = [...blocks.querySelectorAll('.fill')].map((f) => (f as HTMLElement).style.width);
		expect(widths).toEqual(['0%', '100%']);
	});

	it('shows a dash value as sent', () => {
		const view = stats().map((s, i) => (i === 0 ? { ...s, away: '—' } : s));
		const { container } = render(AllStarTeamStats, { props: { stats: view } });
		expect(container.querySelector('.value.away')?.textContent).toBe('—');
	});
});
