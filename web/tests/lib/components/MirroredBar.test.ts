// web/tests/lib/components/MirroredBar.test.ts
//
// Tests for the MirroredBar component.
//
// Tested:
// - The label and both values
// - The better side colored with its team color, the other muted; ink without a color
// - Both halves muted with no better side; — for a missing value
// - The length of each half
//
// What is covered:
// - Each state a bar can show, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/MirroredBar.test.ts
//
// SEE: web/src/lib/components/MirroredBar.svelte
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import MirroredBar from '../../../src/lib/components/MirroredBar.svelte';
import type { BarView } from '../../../src/lib/playoffs/types';

const bar = (change: (b: BarView) => void = () => {}): BarView => {
	const view: BarView = {
		key: 'points',
		label: 'Points per game',
		sides: [
			{ value: '112.4', share: 1, better: true, color: '#1d4e89' },
			{ value: '104.1', share: 0.5, better: false, color: '#2e4057' }
		]
	};
	change(view);
	return view;
};
const fills = (container: HTMLElement) => [...container.querySelectorAll<HTMLElement>('.fill')];

afterEach(() => {
	vi.restoreAllMocks();
});

describe('MirroredBar', () => {
	it('shows the label and both values', () => {
		render(MirroredBar, { props: { bar: bar() } });
		expect(screen.getByText('Points per game')).toBeTruthy();
		expect(screen.getByText('112.4')).toBeTruthy();
		expect(screen.getByText('104.1')).toBeTruthy();
	});

	it('colors the better side and mutes the other', () => {
		const { container } = render(MirroredBar, { props: { bar: bar() } });
		const [left, right] = fills(container);
		expect(left!.classList.contains('better')).toBe(true);
		expect(left!.style.backgroundColor).not.toBe('');
		expect(right!.classList.contains('muted')).toBe(true);
		expect(right!.style.backgroundColor).toBe('');
	});

	it('draws each half at its share', () => {
		const { container } = render(MirroredBar, { props: { bar: bar() } });
		expect(fills(container).map((f) => f.style.inlineSize)).toEqual(['100%', '50%']);
	});

	it('falls back to ink for a better side without a color', () => {
		const { container } = render(MirroredBar, {
			props: { bar: bar((b) => (b.sides[0].color = null)) }
		});
		expect(fills(container)[0]!.classList.contains('ink')).toBe(true);
	});

	it('mutes both halves with no better side and shows — for a missing value', () => {
		const { container } = render(MirroredBar, {
			props: {
				bar: bar((b) => {
					b.sides[0].better = false;
					b.sides[1] = { value: '—', share: 0, better: false, color: null };
				})
			}
		});
		expect(fills(container).map((f) => f.classList.contains('muted'))).toEqual([true, true]);
		expect(screen.getByText('—')).toBeTruthy();
		expect(fills(container)[1]!.style.inlineSize).toBe('0%');
	});
});
