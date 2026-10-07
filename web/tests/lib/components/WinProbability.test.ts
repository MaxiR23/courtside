// web/tests/lib/components/WinProbability.test.ts
//
// Tests for the WinProbability component.
//
// Tested:
// - The y-axis column: home code on top, 50% in the middle, away code at the bottom
// - One line segment and one area segment per pair of points
// - A new point extends the line: earlier segment nodes stay the same objects with the same path
// - The 1000 by 200 viewBox for a game with points past regulation
// - No gridline and no period label without boundaries
// - With boundaries: a gridline at each period start after the first, a label for every period,
//   overtime periods added, the viewBox kept, and a live point extends the line on the same scale
// - The period labels are not inside the plot; the marker is
// - A single point draws no segment, only the latest point marker
//
// What is covered:
// - Live, final, single point and past-regulation states; no layout is asserted
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/WinProbability.test.ts
//
// SEE: web/src/lib/components/WinProbability.svelte
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import WinProbability from '../../../src/lib/components/WinProbability.svelte';

const point = (elapsedSeconds: number, homeWinProbability: number) => ({
	elapsedSeconds,
	homeWinProbability
});
type Boundaries = { periods: { label: string; start: number }[]; end: number } | null;
const chart = (points: ReturnType<typeof point>[], boundaries: Boundaries = null) => ({
	awayCode: 'LAL',
	homeCode: 'GSW',
	middle: '50%',
	points,
	boundaries
});
const regulation: Boundaries = {
	periods: ['Q1', 'Q2', 'Q3', 'Q4'].map((label, i) => ({ label, start: i * 720 })),
	end: 2880
};
const overtime: Boundaries = {
	periods: ['Q1', 'Q2', 'Q3', 'Q4', 'OT1', 'OT2'].map((label, i) => ({
		label,
		start: i < 5 ? i * 720 : 3180
	})),
	end: 3480
};
const labelsOf = (container: HTMLElement) =>
	[...container.querySelectorAll('.periods span')].map((e) => e.textContent);
const live = [point(0, 0.5), point(600, 0.6), point(1200, 0.55)];

describe('WinProbability', () => {
	it('shows the home code on top, 50% in the middle and the away code at the bottom', () => {
		const { container } = render(WinProbability, { props: { chart: chart(live) } });
		const axis = [...container.querySelectorAll('.axis span')].map((e) => e.textContent);
		expect(axis).toEqual(['GSW', '50%', 'LAL']);
	});

	it('draws one line segment and one area segment per pair of points', () => {
		const { container } = render(WinProbability, { props: { chart: chart(live) } });
		expect(container.querySelectorAll('path.line')).toHaveLength(2);
		expect(container.querySelectorAll('path.area')).toHaveLength(2);
		expect(container.querySelector('path.line')?.getAttribute('vector-effect')).toBe(
			'non-scaling-stroke'
		);
	});

	it('extends the line without replacing or changing the existing segments when a point is added', async () => {
		const { container, rerender } = render(WinProbability, { props: { chart: chart(live) } });
		const before = [...container.querySelectorAll('path')];
		const dBefore = before.map((p) => p.getAttribute('d'));
		const groupBefore = container.querySelector('g')?.getAttribute('transform');

		await rerender({ chart: chart([...live, point(1800, 0.7)]) });

		const after = [...container.querySelectorAll('path')];
		expect(after).toHaveLength(before.length + 2);
		before.forEach((node, i) => {
			expect(after[i]).toBe(node);
			expect(node.getAttribute('d')).toBe(dBefore[i]);
		});
		expect(container.querySelector('g')?.getAttribute('transform')).not.toBe(groupBefore);
	});

	it('keeps the 1000 by 200 viewBox for a game with points past regulation', () => {
		const { container } = render(WinProbability, {
			props: { chart: chart([point(0, 0.5), point(2880, 0.4), point(3300, 0.52)]) }
		});
		expect(container.querySelector('svg')?.getAttribute('viewBox')).toBe('0 0 1000 200');
	});

	it('draws no gridline and no period label', () => {
		const { container } = render(WinProbability, { props: { chart: chart(live) } });
		expect(container.querySelectorAll('svg line')).toHaveLength(1); // the 50% line
		expect(container.textContent).not.toMatch(/Q\d|OT\d?/);
	});

	it('draws only the latest point marker for a single point', () => {
		const { container } = render(WinProbability, {
			props: { chart: chart([point(0, 0.75)]) }
		});
		expect(container.querySelectorAll('path')).toHaveLength(0);
		const markers = container.querySelectorAll('.marker');
		expect(markers).toHaveLength(1);
		expect((markers[0] as HTMLElement).style.left).toBe('0%');
		expect((markers[0] as HTMLElement).style.top).toBe('25%');
	});

	it('draws a gridline at each period start after the first and a label for every quarter of a regulation game', () => {
		const { container } = render(WinProbability, { props: { chart: chart(live, regulation) } });
		const lines = [...container.querySelectorAll('line.gridline')];
		expect(lines.map((l) => l.getAttribute('x1'))).toEqual(['250', '500', '750']);
		expect(labelsOf(container)).toEqual(['Q1', 'Q2', 'Q3', 'Q4']);
	});

	it('adds a gridline and a label for every overtime period', () => {
		const points = [point(0, 0.5), point(3300, 0.52)];
		const { container } = render(WinProbability, { props: { chart: chart(points, overtime) } });
		expect(container.querySelectorAll('line.gridline')).toHaveLength(5);
		expect(labelsOf(container)).toEqual(['Q1', 'Q2', 'Q3', 'Q4', 'OT1', 'OT2']);
	});

	it('keeps the period labels outside the plot so the marker maps onto the chart', () => {
		const { container } = render(WinProbability, { props: { chart: chart(live, regulation) } });
		const plot = container.querySelector('.plot') as HTMLElement;
		const periods = container.querySelector('.periods') as HTMLElement;
		expect(plot.contains(periods)).toBe(false);
		expect(plot.querySelector('.marker')).not.toBeNull();
		expect(plot.querySelector('svg')).not.toBeNull();
	});

	it('keeps the 1000 by 200 viewBox with boundaries', () => {
		const { container } = render(WinProbability, { props: { chart: chart(live, overtime) } });
		expect(container.querySelector('svg')?.getAttribute('viewBox')).toBe('0 0 1000 200');
	});

	it('extends the line without changing the scale when a live point is added with boundaries', async () => {
		const { container, rerender } = render(WinProbability, {
			props: { chart: chart(live, regulation) }
		});
		const before = [...container.querySelectorAll('path')];
		const groupBefore = container.querySelector('g')?.getAttribute('transform');

		await rerender({ chart: chart([...live, point(1800, 0.7)], regulation) });

		const after = [...container.querySelectorAll('path')];
		expect(after).toHaveLength(before.length + 2);
		before.forEach((node, i) => expect(after[i]).toBe(node));
		expect(container.querySelector('g')?.getAttribute('transform')).toBe(groupBefore);
	});
});
