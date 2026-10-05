// web/tests/lib/components/NavRow.test.ts
//
// Tests for the NavRow component.
//
// Tested:
// - Shows the brand name, today's date and a Games link to the schedule
// - Hides the brand mark from assistive technology
// - Shows the date and Games in Spanish with a Spanish browser preference
// - Spoiler-free toggle next to Games: off by default, pressed when on, calls its callback
// - Shows the toggle in Spanish
//
// What is covered:
// - Its only state, in English and in Spanish
// - A fixed date, no real clock
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NavRow.test.ts
//
// SEE: web/src/lib/components/NavRow.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { formatDate } from '../../../src/lib/format/locale';
import { preferLanguages } from '../../prefer-languages';

import NavRow from '../../../src/lib/components/NavRow.svelte';

const today = new Date(2026, 9, 4, 12);
const scheduleHref = '/' as ResolvedPathname;
const baseProps = { today, scheduleHref, spoilerFree: false, onSpoilerFreeToggle: () => {} };
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
		render(NavRow, { props: baseProps });
		expect(screen.getByText('Courtside')).toBeTruthy();
	});

	it("shows today's date as Sun, Oct 4, 2026", () => {
		render(NavRow, { props: baseProps });
		expect(screen.getByText('Sun, Oct 4, 2026')).toBeTruthy();
	});

	it('links Games to the schedule', () => {
		render(NavRow, { props: baseProps });
		expect(screen.getByRole('link', { name: 'Games' }).getAttribute('href')).toBe('/');
	});

	it('hides the brand mark from assistive technology', () => {
		const { container } = render(NavRow, { props: baseProps });
		expect(container.querySelector('.brand-mark')?.getAttribute('aria-hidden')).toBe('true');
	});

	it('shows the date and Games in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(NavRow, { props: baseProps });
		expect(screen.getByText(formatDate(today, dateOptions))).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Partidos' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Sin spoilers' })).toBeTruthy();
	});

	it('shows the Spoiler-free toggle off by default next to Games', () => {
		render(NavRow, { props: baseProps });
		const toggle = screen.getByRole('button', { name: 'Spoiler-free' });
		expect(toggle.getAttribute('aria-pressed')).toBe('false');
		expect(screen.getByRole('link', { name: 'Games' }).nextElementSibling).toBe(toggle);
	});

	it('marks the toggle pressed when spoiler-free mode is on', () => {
		render(NavRow, { props: { ...baseProps, spoilerFree: true } });
		expect(screen.getByRole('button', { name: 'Spoiler-free' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
	});

	it('calls onSpoilerFreeToggle when the toggle is clicked', async () => {
		const onSpoilerFreeToggle = vi.fn();
		render(NavRow, { props: { ...baseProps, onSpoilerFreeToggle } });
		await fireEvent.click(screen.getByRole('button', { name: 'Spoiler-free' }));
		expect(onSpoilerFreeToggle).toHaveBeenCalledTimes(1);
	});
});
