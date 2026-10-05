// web/tests/lib/components/DayStrip.test.ts
//
// Tests for the DayStrip component.
//
// Tested:
// - Seven days with Today in the middle, weekday and date number of each
// - Counts in full on desktop and as numbers in compact mode
// - The selected day is marked current; clicking calls onSelect
// - Spanish copy with a Spanish browser preference
//
// What is covered:
// - Desktop, compact, selected and zero-game states, plus interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/DayStrip.test.ts
//
// SEE: web/src/components/DayStrip.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { preferLanguages } from '../../prefer-languages';

import DayStrip from '../../../src/lib/components/DayStrip.svelte';

const counts = [5, 0, 1, 3, 2, 4, 6];
const days = counts.map((gameCount, i) => ({ date: new Date(2026, 9, 1 + i, 12), gameCount }));
const baseProps = { days, selected: 3, compact: false, onSelect: () => {} };

afterEach(() => {
	vi.restoreAllMocks();
});

function cells(container: HTMLElement) {
	return [...container.querySelectorAll<HTMLButtonElement>('button.day')];
}

describe('DayStrip', () => {
	it('shows seven days with Today in the middle', () => {
		const { container } = render(DayStrip, { props: baseProps });
		expect(cells(container)).toHaveLength(7);
		expect(cells(container)[3].textContent).toContain('Today');
	});

	it('shows the weekday and date number of each day', () => {
		const { container } = render(DayStrip, { props: baseProps });
		const text = cells(container).map((c) => c.textContent?.replace(/\s+/g, ' ').trim());
		expect(text[0]).toContain('Thu 1');
		expect(text[3]).toContain('Today 4');
		expect(text[6]).toContain('Wed 7');
	});

	it('shows "5 games", "1 game" and "0 games" on desktop', () => {
		render(DayStrip, { props: baseProps });
		expect(screen.getByText('5 games')).toBeTruthy();
		expect(screen.getByText('1 game')).toBeTruthy();
		expect(screen.getByText('0 games')).toBeTruthy();
	});

	it('shows the count as a number only in compact mode', () => {
		const { container } = render(DayStrip, { props: { ...baseProps, compact: true } });
		expect([...container.querySelectorAll('.count')].map((c) => c.textContent?.trim())).toEqual(
			counts.map(String)
		);
	});

	it('marks the selected day as current', () => {
		const { container } = render(DayStrip, { props: { ...baseProps, selected: 5 } });
		const current = cells(container).filter((c) => c.getAttribute('aria-current') === 'true');
		expect(current).toEqual([cells(container)[5]]);
		expect(container.querySelectorAll('.selected')).toHaveLength(1);
		expect(cells(container)[5].classList.contains('selected')).toBe(true);
	});

	it('calls onSelect with the index of the clicked day', async () => {
		const onSelect = vi.fn();
		const { container } = render(DayStrip, { props: { ...baseProps, onSelect } });
		await fireEvent.click(cells(container)[1]);
		expect(onSelect).toHaveBeenCalledWith(1);
	});

	it('shows Hoy and the count in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(DayStrip, { props: baseProps });
		expect(screen.getByText('Hoy')).toBeTruthy();
		expect(screen.getByText('5 partidos')).toBeTruthy();
		expect(screen.getByText('1 partido')).toBeTruthy();
	});
});
