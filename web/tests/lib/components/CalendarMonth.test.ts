// web/tests/lib/components/CalendarMonth.test.ts
//
// Tests for the CalendarMonth component.
//
// Tested:
// - The month name and the weekday initials, in English and in Spanish
// - The arrows are disabled at the first and the last month, and call their callbacks otherwise
// - A day with games is a link with the href from dayHref and the has-games class
// - A day without games is a span with no href and no tabindex
// - Today has the today class; the selected day has the selected class and aria-current="date"
// - The mobile layout adds the mobile class that picks the smaller cell
// - The day cell and the mark come from tokens in its source
//
// What is covered:
// - The month drawn from props with no fetch; jsdom does no layout, so sizes are asserted in the source
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/CalendarMonth.test.ts
//
// SEE: web/src/lib/components/CalendarMonth.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import CalendarMonth from '../../../src/lib/components/CalendarMonth.svelte';
import { preferLanguages } from '../../prefer-languages';

const props = (changes: Record<string, unknown> = {}) => ({
	month: '1999-02',
	days: new Set(['1999-02-05', '1999-02-06', '1999-02-09']),
	today: '1999-02-06',
	selected: '1999-02-05',
	canPrevious: true,
	canNext: true,
	onPrevious: vi.fn(),
	onNext: vi.fn(),
	dayHref: (date: string) => `/day/${date}` as ResolvedPathname,
	layout: 'desktop' as const,
	...changes
});

afterEach(() => {
	vi.restoreAllMocks();
});

describe('CalendarMonth', () => {
	it('shows the month name and the weekday initials', () => {
		const { container } = render(CalendarMonth, { props: props() });
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('February 1999');
		expect([...container.querySelectorAll('.weekday')].map((el) => el.textContent)).toEqual([
			'S',
			'M',
			'T',
			'W',
			'T',
			'F',
			'S'
		]);
	});

	it('shows the month name and the weekday initials in Spanish', () => {
		preferLanguages(['es-ES']);
		const { container } = render(CalendarMonth, { props: props() });
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('febrero de 1999');
		expect([...container.querySelectorAll('.weekday')].map((el) => el.textContent)).toEqual([
			'D',
			'L',
			'M',
			'X',
			'J',
			'V',
			'S'
		]);
		expect(screen.getByRole('button', { name: 'Mes anterior' })).toBeTruthy();
	});

	it('disables the arrows at the ends and calls the callbacks otherwise', async () => {
		const onPrevious = vi.fn();
		const onNext = vi.fn();
		render(CalendarMonth, { props: props({ onPrevious, onNext }) });
		await fireEvent.click(screen.getByRole('button', { name: 'Previous month' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Next month' }));
		expect(onPrevious).toHaveBeenCalledTimes(1);
		expect(onNext).toHaveBeenCalledTimes(1);
	});

	it('disables the previous arrow at the first month and the next arrow at the last', () => {
		const { unmount } = render(CalendarMonth, { props: props({ canPrevious: false }) });
		expect(
			(screen.getByRole('button', { name: 'Previous month' }) as HTMLButtonElement).disabled
		).toBe(true);
		expect((screen.getByRole('button', { name: 'Next month' }) as HTMLButtonElement).disabled).toBe(
			false
		);
		unmount();
		render(CalendarMonth, { props: props({ canNext: false }) });
		expect((screen.getByRole('button', { name: 'Next month' }) as HTMLButtonElement).disabled).toBe(
			true
		);
	});

	it('draws a day with games as a link and a day without as a plain span', () => {
		const { container } = render(CalendarMonth, { props: props() });
		const link = screen.getByRole('link', { name: 'February 9, 1999' });
		expect(link.getAttribute('href')).toBe('/day/1999-02-09');
		expect(link.classList.contains('has-games')).toBe(true);
		expect(container.querySelectorAll('a.day')).toHaveLength(3);
		const off = screen.getByText('7');
		expect(off.tagName).toBe('SPAN');
		expect(off.hasAttribute('href')).toBe(false);
		expect(off.hasAttribute('tabindex')).toBe(false);
		expect(off.classList.contains('off')).toBe(true);
	});

	it('marks today and the selected day', () => {
		render(CalendarMonth, { props: props() });
		const today = screen.getByRole('link', { name: 'February 6, 1999' });
		expect(today.classList.contains('today')).toBe(true);
		expect(today.classList.contains('selected')).toBe(false);
		const selected = screen.getByRole('link', { name: 'February 5, 1999' });
		expect(selected.classList.contains('selected')).toBe(true);
		expect(selected.getAttribute('aria-current')).toBe('date');
		expect(today.getAttribute('aria-current')).toBeNull();
	});

	it('adds the mobile class on the mobile layout', () => {
		const { container } = render(CalendarMonth, { props: props({ layout: 'mobile' }) });
		expect(container.querySelector('.month')?.classList.contains('mobile')).toBe(true);
	});

	it('takes the cell sizes and the mark from tokens', () => {
		const source = readFileSync(
			join(__dirname, '..', '..', '..', 'src', 'lib', 'components', 'CalendarMonth.svelte'),
			'utf8'
		);
		expect(source).toContain('width: var(--past-day-cell)');
		expect(source).toContain('width: var(--past-day-cell-mobile)');
		expect(source).toContain('width: var(--past-day-mark)');
		expect(source).toContain('color: var(--past-day-off-ink)');
	});
});
