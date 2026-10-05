// web/tests/lib/components/NavRow.test.ts
//
// Tests for the NavRow component.
//
// Tested:
// - Shows the brand name, today's date and a Games link to the schedule
// - Hides the brand mark from assistive technology
// - Shows the date and Games in Spanish with a Spanish browser preference
//
// What is covered:
// - Its only state, in English and in Spanish
// - A fixed date, no real clock
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NavRow.test.ts
//
// SEE: web/src/lib/components/NavRow.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { formatDate } from '../../../src/lib/format/locale';
import { preferLanguages } from '../../prefer-languages';

import NavRow from '../../../src/lib/components/NavRow.svelte';

const today = new Date(2026, 9, 4, 12);
const scheduleHref = '/' as ResolvedPathname;
const dateOptions: Intl.DateTimeFormatOptions = {
	weekday: 'short',
	month: 'short',
	day: 'numeric',
	year: 'numeric'
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('NavRow', () => {
	it('shows the brand name', () => {
		render(NavRow, { props: { today, scheduleHref } });
		expect(screen.getByText('Courtside')).toBeTruthy();
	});

	it("shows today's date as Sun, Oct 4, 2026", () => {
		render(NavRow, { props: { today, scheduleHref } });
		expect(screen.getByText('Sun, Oct 4, 2026')).toBeTruthy();
	});

	it('links Games to the schedule', () => {
		render(NavRow, { props: { today, scheduleHref } });
		expect(screen.getByRole('link', { name: 'Games' }).getAttribute('href')).toBe('/');
	});

	it('hides the brand mark from assistive technology', () => {
		const { container } = render(NavRow, { props: { today, scheduleHref } });
		expect(container.querySelector('.brand-mark')?.getAttribute('aria-hidden')).toBe('true');
	});

	it('shows the date and Games in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(NavRow, { props: { today, scheduleHref } });
		expect(screen.getByText(formatDate(today, dateOptions))).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Partidos' })).toBeTruthy();
	});
});
