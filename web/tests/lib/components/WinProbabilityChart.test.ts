// web/tests/lib/components/WinProbabilityChart.test.ts
//
// Tests for the WinProbabilityChart component.
//
// Tested:
// - The svg with its aria label, one gridline per period after the first and a dashed midline
// - One line segment per pair of points
// - The largest deficit marker and label at its place, none when the feed has no deficit
//
// What is covered:
// - Each state the chart shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/WinProbabilityChart.test.ts
//
// SEE: web/src/lib/components/WinProbabilityChart.svelte
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import WinProbabilityChart from '../../../src/lib/components/WinProbabilityChart.svelte';
import type { FinalsChartView } from '../../../src/lib/playoffs/types';

const chart = (change: (c: FinalsChartView) => void = () => {}): FinalsChartView => {
	const view: FinalsChartView = {
		points: [
			{ elapsedSeconds: 0, homeWinProbability: 0.5 },
			{ elapsedSeconds: 1500, homeWinProbability: 0.62 },
			{ elapsedSeconds: 2880, homeWinProbability: 1 }
		],
		boundaries: {
			periods: [
				{ label: '1', start: 0 },
				{ label: '2', start: 720 },
				{ label: '3', start: 1440 },
				{ label: '4', start: 2160 }
			],
			end: 2880
		},
		deficit: { label: 'Largest deficit: 12', left: 0.3 }
	};
	change(view);
	return view;
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('WinProbabilityChart', () => {
	it('draws the svg with its label, the quarter dividers and the dashed midline', () => {
		const { container } = render(WinProbabilityChart, { props: { chart: chart() } });
		expect(screen.getByRole('img', { name: 'Win probability' })).toBeTruthy();
		expect(container.querySelectorAll('.gridline')).toHaveLength(3);
		expect(container.querySelectorAll('.midline')).toHaveLength(1);
		expect(container.querySelector('svg')?.getAttribute('preserveAspectRatio')).toBe('none');
	});

	it('draws one line segment per pair of points', () => {
		const { container } = render(WinProbabilityChart, { props: { chart: chart() } });
		expect(container.querySelectorAll('.line')).toHaveLength(2);
	});

	it('draws the deficit marker with its label at its place', () => {
		const { container } = render(WinProbabilityChart, { props: { chart: chart() } });
		const marker = container.querySelector('.deficit') as HTMLElement;
		expect(marker.style.left).toBe('30%');
		expect(marker.classList.contains('flip')).toBe(false);
		expect(screen.getByText('Largest deficit: 12')).toBeTruthy();
	});

	it('flips the label near the right edge', () => {
		const { container } = render(WinProbabilityChart, {
			props: { chart: chart((c) => (c.deficit = { label: 'Largest deficit: 9', left: 0.9 })) }
		});
		expect(container.querySelector('.deficit')?.classList.contains('flip')).toBe(true);
	});

	it('draws no marker without a deficit and no dividers without boundaries', () => {
		const { container } = render(WinProbabilityChart, {
			props: {
				chart: chart((c) => {
					c.deficit = null;
					c.boundaries = null;
				})
			}
		});
		expect(container.querySelector('.deficit')).toBeNull();
		expect(container.querySelectorAll('.gridline')).toHaveLength(0);
	});
});
