// web/tests/lib/components/ComingUp.test.ts
//
// Tests for the ComingUp component.
//
// Tested:
// - Desktop: an aside with a blueprint frame, its four corner marks and the "Coming up" header
// - Mobile: a section (no aside) with the same items
// - Each item shows its date, title, sub line and status chip; Now carries the accent class
// - The call to action links to /cup, /all-star and /playoffs by target and is absent for a null target
// - Spanish copy with a Spanish browser preference
//
// What is covered:
// - Each status, items with and without a link, both layouts
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/ComingUp.test.ts
//
// SEE: web/src/lib/components/ComingUp.svelte
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ComingUp from '../../../src/lib/components/ComingUp.svelte';
import type { ComingUpItemView } from '../../../src/lib/home/types';
import { preferLanguages } from '../../prefer-languages';

const items: ComingUpItemView[] = [
	{
		key: 'openingNight',
		date: 'Oct 4',
		title: 'Opening Night',
		sub: 'The regular season begins',
		status: 'done',
		statusLabel: 'Done',
		target: null
	},
	{
		key: 'cupGroupStage',
		date: 'Nov 4 – Dec 3',
		title: 'Cup group play',
		sub: 'In-season tournament · Group stage',
		status: 'now',
		statusLabel: 'Now',
		target: 'cup'
	},
	{
		key: 'allStar',
		date: 'Feb 14',
		title: 'All-Star',
		sub: 'The midseason showcase',
		status: 'upcoming',
		statusLabel: 'Upcoming',
		target: 'allStar'
	},
	{
		key: 'playoffs',
		date: 'Apr 18',
		title: 'Playoffs',
		sub: 'The first round begins',
		status: 'upcoming',
		statusLabel: 'Upcoming',
		target: 'playoffs'
	}
];

afterEach(() => {
	vi.restoreAllMocks();
});

describe('ComingUp on desktop', () => {
	it('is an aside with a blueprint frame and the header', () => {
		const { container } = render(ComingUp, { props: { items, layout: 'desktop' } });
		expect(container.querySelector('aside.coming-up')).not.toBeNull();
		expect(container.querySelector('section')).toBeNull();
		expect(container.querySelectorAll('.blueprint-mark')).toHaveLength(4);
		expect(screen.getByRole('complementary', { name: 'Coming up' })).toBeTruthy();
	});

	it('shows the date, title, sub line and status of every item', () => {
		render(ComingUp, { props: { items, layout: 'desktop' } });
		expect(screen.getAllByRole('listitem')).toHaveLength(4);
		for (const item of items) {
			expect(screen.getByText(item.date)).toBeTruthy();
			expect(screen.getByText(item.title)).toBeTruthy();
			expect(screen.getByText(item.sub)).toBeTruthy();
		}
		expect(screen.getByText('Done')).toBeTruthy();
		expect(screen.getAllByText('Upcoming')).toHaveLength(2);
	});

	it('marks only the Now status with the accent', () => {
		render(ComingUp, { props: { items, layout: 'desktop' } });
		expect(screen.getByText('Now').classList.contains('out')).toBe(true);
		expect(screen.getByText('Done').classList.contains('out')).toBe(false);
		expect(screen.getAllByText('Upcoming')[0].classList.contains('out')).toBe(false);
	});

	it('links each item with a target to its page and leaves the others without a link', () => {
		render(ComingUp, { props: { items, layout: 'desktop' } });
		expect(screen.getByRole('link', { name: 'Cup →' }).getAttribute('href')).toBe('/cup');
		expect(screen.getByRole('link', { name: 'All-Star →' }).getAttribute('href')).toBe('/all-star');
		expect(screen.getByRole('link', { name: 'Playoffs →' }).getAttribute('href')).toBe('/playoffs');
		expect(screen.getAllByRole('link')).toHaveLength(3);
	});
});

describe('ComingUp on mobile', () => {
	it('is a section with the same items and no aside', () => {
		const { container } = render(ComingUp, { props: { items, layout: 'mobile' } });
		expect(container.querySelector('aside')).toBeNull();
		expect(container.querySelector('section.coming-up.mobile')).not.toBeNull();
		expect(screen.getByRole('region', { name: 'Coming up' })).toBeTruthy();
		expect(screen.getAllByRole('listitem')).toHaveLength(4);
		expect(container.querySelectorAll('.blueprint-mark')).toHaveLength(4);
	});
});

describe('ComingUp in Spanish', () => {
	it('shows the header and the calls to action in Spanish', () => {
		preferLanguages(['es']);
		render(ComingUp, { props: { items, layout: 'desktop' } });
		expect(screen.getByRole('complementary', { name: 'Próximamente' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Copa →' })).toBeTruthy();
	});
});
