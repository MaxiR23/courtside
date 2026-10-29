// web/tests/lib/components/TeamRecord.test.ts
//
// Tests for the TeamRecord component.
//
// Tested:
// - The large cells with their value and win percentage, in order
// - The detail cells with their sub line only when given, in order
// - The large values use the record size; all values are strong and in tabular figures
//
// What is covered:
// - Both rows
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamRecord.test.ts
//
// SEE: web/src/lib/components/TeamRecord.svelte
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TeamRecord from '../../../src/lib/components/TeamRecord.svelte';
import type { RecordSection } from '../../../src/lib/team/types';

const record: RecordSection = {
	meta: '2025-26 · regular season',
	large: [
		{ label: 'Overall', value: '57–25', sub: '69.5%' },
		{ label: 'Home', value: '32–9', sub: '78.0%' },
		{ label: 'Away', value: '25–16', sub: '61.0%' },
		{ label: 'Last 10', value: '8–2', sub: '80.0%' }
	],
	detail: [
		{ label: 'Streak', value: 'W3', sub: null },
		{ label: 'Points for', value: '118.3', sub: '9,701' },
		{ label: 'Differential', value: '+8.4', sub: '+689' }
	]
};

const texts = (container: HTMLElement, row: number) =>
	[...(container.querySelectorAll('.cells')[row]?.querySelectorAll('.cell') ?? [])].map((cell) =>
		[...cell.querySelectorAll('span')].map((span) => span.textContent)
	);

describe('TeamRecord', () => {
	it('shows the four large cells in order with their win percentage', () => {
		const { container } = render(TeamRecord, { props: { record } });
		expect(texts(container, 0)).toEqual([
			['Overall', '57–25', '69.5%'],
			['Home', '32–9', '78.0%'],
			['Away', '25–16', '61.0%'],
			['Last 10', '8–2', '80.0%']
		]);
	});

	it('still renders both grid elements for empty lists', () => {
		const { container } = render(TeamRecord, {
			props: { record: { ...record, large: [], detail: [] } }
		});
		expect(container.querySelectorAll('.cells')).toHaveLength(2);
		expect(container.querySelectorAll('.cell')).toHaveLength(0);
	});

	it('shows the detail cells in order, with a sub line only when there is one', () => {
		const { container } = render(TeamRecord, { props: { record } });
		expect(texts(container, 1)).toEqual([
			['Streak', 'W3'],
			['Points for', '118.3', '9,701'],
			['Differential', '+8.4', '+689']
		]);
	});

	it('draws the large values at the record size, and every value strong and numeric', () => {
		const { container } = render(TeamRecord, { props: { record } });
		const [large, detail] = [...container.querySelectorAll('.cells')];
		for (const value of large!.querySelectorAll('.value')) {
			expect(value.classList.contains('record')).toBe(true);
		}
		for (const value of detail!.querySelectorAll('.value')) {
			expect(value.classList.contains('record')).toBe(false);
		}
		for (const value of container.querySelectorAll('.value')) {
			expect(value.classList.contains('strong')).toBe(true);
			expect(value.classList.contains('numeric')).toBe(true);
		}
	});
});
