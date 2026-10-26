// web/tests/lib/components/ScheduleEmptyDay.test.ts
//
// Tests for the empty-day box of the home schedule.
//
// Tested:
// - The title and the next games text
// - The Go to button links to the href windowHref gives, with its label, when goTo is set
// - No link at all when goTo is null; the two-weeks text
// - No href starts with /day/
//
// What is covered:
// - Each state of the view (with and without goTo)
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/ScheduleEmptyDay.test.ts
//
// SEE: web/src/lib/components/ScheduleEmptyDay.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import type { EmptyDayView } from '../../../src/lib/home/types';

import ScheduleEmptyDay from '../../../src/lib/components/ScheduleEmptyDay.svelte';

const windowHref = (date: string) => `/?day=${date}` as ResolvedPathname;
const withGoTo: EmptyDayView = {
	title: 'No games on this day',
	text: 'Next games: Tue, Oct 6 · 5 games',
	goTo: { date: '2026-10-06', label: 'Go to Tue, Oct 6 →' }
};

describe('ScheduleEmptyDay', () => {
	it('shows the title, the text and the Go to link', () => {
		const { container } = render(ScheduleEmptyDay, { props: { view: withGoTo, windowHref } });
		expect(screen.getByRole('heading', { name: 'No games on this day' })).toBeTruthy();
		expect(screen.getByText('Next games: Tue, Oct 6 · 5 games')).toBeTruthy();
		const link = screen.getByRole('link', { name: 'Go to Tue, Oct 6 →' });
		expect(link.getAttribute('href')).toBe('/?day=2026-10-06');
		for (const a of container.querySelectorAll('a')) {
			expect(a.getAttribute('href')?.startsWith('/day/')).toBe(false);
		}
	});

	it('shows no link when goTo is null', () => {
		const view = { ...withGoTo, text: 'No games scheduled in the next two weeks.', goTo: null };
		const { container } = render(ScheduleEmptyDay, { props: { view, windowHref } });
		expect(screen.getByText('No games scheduled in the next two weeks.')).toBeTruthy();
		expect(container.querySelector('a')).toBeNull();
	});
});
